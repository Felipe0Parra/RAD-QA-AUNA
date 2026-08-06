"""Z11 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md §6.4-S7/§7): la
herramienta de migración (`scripts/migrar_bd_a_estandar.py`) informa el
estado del índice único de controles (U2, `idx_controles_unico_mes`) --
antes el índice se creaba (o no) en silencio, sin que la sección "Cambios
estructurales" del reporte lo mencionara.

Tres estados posibles, nunca ninguno:
- "creado" (no existía antes, existe después)
- "ya existía" (segunda corrida, idempotente)
- "NO CREADO -- hay N grupo(s) duplicado(s)" (bloqueado por U1, sin borrar
  ni corregir nada)
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.migrar_bd_a_estandar import migrar

CABECERA_SQLITE = b"SQLite format 3\x00"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _bd_vacia_valida(ruta):
    """Un archivo SQLite válido sin ningún esquema de la app -- migrar()
    debe correr el arranque completo desde cero sobre él."""
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE _dummy (id INTEGER)")
    con.commit()
    con.close()


def _indice_existe(ruta):
    con = sqlite3.connect(ruta)
    try:
        return bool(con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' "
            "AND name='idx_controles_unico_mes'").fetchone())
    finally:
        con.close()


class TestBdLimpiaInformaCreado:
    def test_primera_corrida_informa_creado(self, app, tmp_path, capsys):
        ruta = str(tmp_path / "nueva.db")
        _bd_vacia_valida(ruta)

        capsys.readouterr()
        migrar(ruta, aplicar=True)
        salida = capsys.readouterr().out

        assert _indice_existe(ruta)
        assert "Índice único de controles: creado" in salida


class TestSegundaCorridaInformaYaExistia:
    def test_segunda_corrida_informa_ya_existia(self, app, tmp_path, capsys):
        ruta = str(tmp_path / "nueva.db")
        _bd_vacia_valida(ruta)
        migrar(ruta, aplicar=True)  # primera corrida: crea el índice

        capsys.readouterr()
        migrar(ruta, aplicar=True)  # segunda corrida: idempotente
        salida = capsys.readouterr().out

        assert _indice_existe(ruta)
        assert "Índice único de controles: ya existía" in salida


class TestBdConDuplicadosInformaElBloqueoSinBorrarNada:
    def test_duplicados_bloquean_y_se_reportan(self, app, monkeypatch, tmp_path, capsys):
        ruta = str(tmp_path / "con_duplicados.db")
        # BD real (esquema completo, índice ya creado sin duplicados) --
        # mismo bootstrap que usa la app, vía Conexion() real.
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        conexion = Conexion()
        con = conexion.con
        con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)",
            ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
        # DROP INDEX antes de insertar duplicados -- si no, el propio
        # índice (ya creado por el bootstrap de arriba, sin duplicados
        # todavía) rechazaría el segundo INSERT.
        con.execute("DROP INDEX idx_controles_unico_mes")
        con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
            ("Clinac 600", "Mensual", "08/2026"))
        con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
            ("Clinac 600", "Mensual", "20/08/2026"))
        con.commit()
        conteo_antes = con.execute("SELECT COUNT(*) FROM controles").fetchone()[0]
        con.close()
        Conexion._instance = None

        capsys.readouterr()
        migrar(ruta, aplicar=True)
        salida = capsys.readouterr().out

        assert not _indice_existe(ruta), "no debía crear el índice habiendo duplicados"
        assert "Índice único de controles: NO CREADO" in salida
        assert "duplicado" in salida.lower()

        con2 = sqlite3.connect(ruta)
        conteo_despues = con2.execute("SELECT COUNT(*) FROM controles").fetchone()[0]
        con2.close()
        assert conteo_despues == conteo_antes, "no debía borrar ninguna fila"
