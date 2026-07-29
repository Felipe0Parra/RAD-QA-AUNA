"""F1 (PLAN_F_CIERRE_ESTANDAR_29-07.md): copia de seguridad ANTES de que
`_asegurar_fk_on_delete_restrict` (E10) recree tablas al arranque.

Antes de F1: E9 respalda al CERRAR (`closeEvent`); E10 migra al ABRIR
(`Conexion.__init_connection`). Verificado sobre la BD de producción real
(2026-07-29): la primera vez que un build nuevo abre un archivo aún en
CASCADE, recrea 59 tablas antes de que exista ningún respaldo de esa sesión.

Esta suite fija el contrato:
- BD ya migrada (o nueva, nacida en RESTRICT): no se crea ningún respaldo
  extra -- ni carpeta ni archivo.
- BD legada (con CASCADE): se crea un respaldo ANTES de recrear, íntegro
  (integrity_check=ok, mismos datos que el estado previo a migrar).
- Si el respaldo no puede escribirse, la migración estructural NO se
  ejecuta ese arranque -- la BD queda tal como estaba (CASCADE), la app
  arranca sin excepción, y se reintenta en el siguiente arranque.
- El respaldo previo vive en una subcarpeta propia (`pre_migracion/`), que
  la rotación de los cierres diarios (E9, `respaldos_bd/` a secas) no puede
  desalojar.
"""
import os
import sqlite3
import stat

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.respaldo import carpeta_respaldos


def _bd_legada(tmp_path, monkeypatch, nombre="legada.db"):
    """Subconjunto real del esquema PRE-E10 (mismo patrón que
    test_e10_restrict.py::TestMigracionDeBdLegada)."""
    ruta = str(tmp_path / nombre)
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE controles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo TEXT, control TEXT, fecha TEXT,
            user_id TEXT, user_id_f2 TEXT);
        CREATE TABLE dosimetriaMen (
            ref INTEGER, energia TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE CASCADE ON UPDATE CASCADE);
    """)
    con.execute("INSERT INTO controles (equipo, control, fecha) "
                "VALUES ('Clinac iX', 'Mensual', '01/2026')")
    con.execute("INSERT INTO dosimetriaMen (ref, energia) VALUES (1, '6mv')")
    con.commit()
    con.close()
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    return ruta


def _cerrar(conexion):
    conexion.con.close()
    Conexion._instance = None


class TestBdYaAlDiaNoRespaldaDeMas:
    def test_bd_nueva_no_crea_carpeta_de_respaldo_previo(self, tmp_path, monkeypatch):
        ruta = str(tmp_path / "nueva.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        conexion = Conexion()  # DDL actual: nace en RESTRICT, nada que migrar
        try:
            carpeta = os.path.join(carpeta_respaldos(ruta), "pre_migracion")
            assert not os.path.isdir(carpeta)
        finally:
            _cerrar(conexion)


class TestBdLegadaSeRespaldaAntesDeMigrar:
    def test_se_crea_un_respaldo_previo_integro(self, tmp_path, monkeypatch):
        ruta = _bd_legada(tmp_path, monkeypatch)
        conexion = Conexion()  # arranque real: dispara F1 y luego E10
        try:
            carpeta = os.path.join(carpeta_respaldos(ruta), "pre_migracion")
            archivos = os.listdir(carpeta)
            assert len(archivos) == 1
            respaldo = os.path.join(carpeta, archivos[0])

            con = sqlite3.connect(respaldo)
            try:
                assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                # el respaldo conserva el estado ANTERIOR a la migración
                acciones = {fk[6] for fk in con.execute(
                    "PRAGMA foreign_key_list('dosimetriaMen')").fetchall()}
                assert acciones == {"CASCADE"}
                fila = con.execute(
                    "SELECT ref, energia FROM dosimetriaMen").fetchone()
                assert fila == (1, "6mv")
            finally:
                con.close()
        finally:
            _cerrar(conexion)

    def test_la_migracion_real_si_ocurre_tras_el_respaldo(self, tmp_path, monkeypatch):
        ruta = _bd_legada(tmp_path, monkeypatch)
        conexion = Conexion()
        try:
            con = sqlite3.connect(ruta)
            try:
                acciones = {fk[6] for fk in con.execute(
                    "PRAGMA foreign_key_list('dosimetriaMen')").fetchall()}
            finally:
                con.close()
            assert acciones == {"RESTRICT"}
        finally:
            _cerrar(conexion)

    def test_el_respaldo_previo_no_lo_desaloja_la_rotacion_de_cierres(
            self, tmp_path, monkeypatch):
        """El respaldo de F1 vive en una subcarpeta propia
        (`respaldos_bd/pre_migracion/`), distinta de la carpeta donde E9
        rota las copias de cada cierre (`respaldos_bd/` a secas) -- nunca
        compiten por el mismo cupo de rotación."""
        ruta = _bd_legada(tmp_path, monkeypatch)
        conexion = Conexion()
        try:
            carpeta_cierres = carpeta_respaldos(ruta)
            carpeta_previa = os.path.join(carpeta_cierres, "pre_migracion")
            assert os.path.isdir(carpeta_previa)
            assert os.path.dirname(carpeta_previa) == carpeta_cierres
            # y el respaldo previo no aparece en el listado de cierres:
            archivos_en_cierres = [f for f in os.listdir(carpeta_cierres)
                                    if os.path.isfile(os.path.join(carpeta_cierres, f))]
            assert archivos_en_cierres == []
        finally:
            _cerrar(conexion)


class TestSiElRespaldoFallaNoSeMigra:
    def test_carpeta_destino_no_escribible_aborta_la_migracion(self, tmp_path, monkeypatch):
        ruta = _bd_legada(tmp_path, monkeypatch)
        carpeta_bloqueada = os.path.join(carpeta_respaldos(ruta))
        os.makedirs(carpeta_bloqueada, exist_ok=True)
        modo_original = os.stat(carpeta_bloqueada).st_mode
        os.chmod(carpeta_bloqueada, stat.S_IREAD | stat.S_IEXEC)  # sin escritura
        try:
            conexion = Conexion()  # no debe lanzar
            try:
                con = sqlite3.connect(ruta)
                try:
                    acciones = {fk[6] for fk in con.execute(
                        "PRAGMA foreign_key_list('dosimetriaMen')").fetchall()}
                    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                finally:
                    con.close()
                # sin respaldo posible, la migración se posterga: sigue en CASCADE
                assert acciones == {"CASCADE"}
                fila = con2 = sqlite3.connect(ruta)
                try:
                    assert con2.execute(
                        "SELECT ref, energia FROM dosimetriaMen").fetchone() == (1, "6mv")
                finally:
                    con2.close()
            finally:
                _cerrar(conexion)
        finally:
            os.chmod(carpeta_bloqueada, modo_original)

    def test_se_reintenta_en_el_siguiente_arranque(self, tmp_path, monkeypatch):
        """Tras un fallo de respaldo, un arranque posterior con la carpeta
        ya escribible sí completa la migración -- F1 no deja la BD varada
        para siempre en CASCADE."""
        ruta = _bd_legada(tmp_path, monkeypatch)
        carpeta_bloqueada = carpeta_respaldos(ruta)
        os.makedirs(carpeta_bloqueada, exist_ok=True)
        os.chmod(carpeta_bloqueada, stat.S_IREAD | stat.S_IEXEC)
        conexion = Conexion()
        _cerrar(conexion)

        os.chmod(carpeta_bloqueada, stat.S_IRWXU)  # ya escribible
        conexion = Conexion()  # segundo arranque
        try:
            con = sqlite3.connect(ruta)
            try:
                acciones = {fk[6] for fk in con.execute(
                    "PRAGMA foreign_key_list('dosimetriaMen')").fetchall()}
            finally:
                con.close()
            assert acciones == {"RESTRICT"}
        finally:
            _cerrar(conexion)
