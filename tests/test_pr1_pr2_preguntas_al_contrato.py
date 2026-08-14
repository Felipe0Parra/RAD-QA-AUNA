"""PR1+PR2 (PLAN_CONTRATO_GUARDADO_13-08.md §6-PR1/PR2): última tabla del
inventario -- `preguntas` entra a `TABLAS_ANULABLES` y hereda, sin tocar de
nuevo su código de guardado, la transformación anular+insertar que DO1 ya
escribió en `subirlineasmensuales` (misma rama `if nombre_tabla in
TABLAS_ANULABLES and "activo" in columnas_reales_tabla`).

`preguntas` tiene una particularidad que ninguna otra tabla del bloque
comparte: su última columna real, `imagen` (BLOB), queda FUERA de
`columnas_lista` -- `encontrar_columnas(..., delete=1)` la recorta a
propósito porque se guarda por su propio camino (`crear_algo`/`dbImagen`,
el botón "Guardar análisis"), no por el guardado de texto de aspectos
mecánicos. Componer el bloque nuevo solo con `columnas_lista` (como hacía
la primera versión de DO1) perdería esa columna en cada bloque NUEVO: una
fila insertada sin especificarla queda NULL, orfanando en silencio
cualquier imagen ya subida -- el bloque viejo la conserva (queda
`activo=0` pero intacto) pero deja de ser el que el físico ve. Se detectó
al implementar PR1 (nunca había ocurrido antes: DO1 solo tenía
`dosimetriaMen`, sin columnas recortadas) y se corrigió componiendo desde
el esquema COMPLETO (`columnas_completas`), no solo el recortado.
"""
import os
import sqlite3
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import subirlineasmensuales, crear_algo
from scripts.indices_bloque_qc import crear_indices, nombre_indice
from services.anulacion import TABLAS_ANULABLES
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + migraciones reales, incl. _asegurar_activo_bloque_qc
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sin_avisos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


def _crear_control_activo(ruta_bd, control_id, equipo="Clinac 600"):
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, ?, 'Mensual', '01/2026', 'Físico de Prueba')",
        (control_id, equipo))
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(control_id)))
    con.commit()
    con.close()


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _pelado_preguntas():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    return obj


def _filas_preguntas(ruta_bd, ref):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT rowid, iso_mec, imagen, activo FROM preguntas "
        "WHERE ref = ? ORDER BY rowid", (ref,)).fetchall()
    con.close()
    return filas


def _audit_log_preguntas(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT accion, tabla, ref FROM audit_log WHERE tabla = 'preguntas'"
    ).fetchall()
    con.close()
    return filas


class TestPR1EsquemaYListaBlanca:
    def test_preguntas_esta_en_tablas_anulables(self):
        assert "preguntas" in TABLAS_ANULABLES

    def test_preguntas_gana_columna_activo(self, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        columnas = {r[1] for r in con.execute("PRAGMA table_info(preguntas)")}
        con.close()
        assert "activo" in columnas

    def test_indice_bloque_qc_se_crea_para_preguntas(self, bd_temporal):
        resultado = crear_indices(bd_temporal)
        assert resultado["preguntas"] == "creado", resultado["preguntas"]

        con = sqlite3.connect(bd_temporal)
        existe = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
            (nombre_indice("preguntas"),)).fetchone()
        con.close()
        assert existe is not None


class TestPR2GuardadoAnulaEInserta:
    """Mismo contrato ya probado para dosimetriaMen en DO2, ahora sobre
    `preguntas` -- prueba que la rama anulable NO es específica de
    dosimetriaMen, se activó sola con la lista blanca (PR1)."""

    def test_corregir_un_campo_conserva_la_version_anterior(
            self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 950)

        obj = _pelado_preguntas()
        obj.lbl_iso_mec = QLineEdit("0.50")
        obj.df_lines = ["lbl_iso_mec"]
        subirlineasmensuales(obj, "preguntas", 1, ref=950, usarid=False)

        obj2 = _pelado_preguntas()
        obj2.lbl_iso_mec = QLineEdit("0.90")  # el físico corrige
        obj2.df_lines = ["lbl_iso_mec"]
        subirlineasmensuales(obj2, "preguntas", 1, ref=950, usarid=False)

        filas = _filas_preguntas(bd_temporal, 950)
        assert len(filas) == 2, (
            f"la corrección debía dejar 2 filas -- la vieja histórica, la "
            f"nueva vigente: {filas}")
        valores_por_activo = {activo: iso_mec for _, iso_mec, _, activo in filas}
        assert valores_por_activo == {0: 0.5, 1: 0.9}, (
            f"el valor viejo (0.5) debía quedar activo=0, el corregido "
            f"(0.9) activo=1: {filas}")

        # DA-05: "corrección con rastro" -- las dos escrituras quedan
        # auditadas (no solo la última).
        assert len(_audit_log_preguntas(bd_temporal)) == 2

    def test_invariante_3_guardado_sin_columna_real_no_anula_lo_vigente(
            self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 951)

        obj = _pelado_preguntas()
        obj.lbl_iso_mec = QLineEdit("0.5")
        obj.df_lines = ["lbl_iso_mec"]
        subirlineasmensuales(obj, "preguntas", 1, ref=951, usarid=False)

        # Un widget huérfano (nombre que no mapea a ninguna columna real de
        # `preguntas`) no debe anular ni tocar la fila ya guardada.
        obj2 = _pelado_preguntas()
        obj2.lbl_widget_huerfano = QLineEdit("99")
        obj2.df_lines = ["lbl_widget_huerfano"]
        subirlineasmensuales(obj2, "preguntas", 1, ref=951, usarid=False)

        filas = _filas_preguntas(bd_temporal, 951)
        assert len(filas) == 1, (
            f"un guardado sin columnas reales no debía tocar la fila: {filas}")
        assert filas[0][1] == 0.5
        assert filas[0][3] == 1


class TestPR1ImagenSobreviveAlReemplazoDeBloque:
    """El hallazgo específico de PR1: `imagen` queda fuera de
    `columnas_lista` (recortada por `encontrar_columnas(delete=1)`) porque
    se guarda por su propio camino (`crear_algo`, el botón "Guardar
    análisis"). Un resave de texto NO debe orfanarla."""

    def test_resave_de_texto_no_orfana_la_imagen(
            self, app, bd_temporal, monkeypatch, tmp_path):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 952)

        imagen_bytes = b"contenido binario de prueba -- simula un analisis de placa"
        ruta_imagen = tmp_path / "analisis.png"
        ruta_imagen.write_bytes(imagen_bytes)

        # 1. El físico sube la imagen del análisis (crear_algo/dbImagen,
        # camino real de "Guardar análisis" -- INSERT porque no hay fila
        # previa para este ref).
        obj_imagen = _pelado_preguntas()
        obj_imagen.imagen_path = str(ruta_imagen)
        crear_algo(obj_imagen, 952, None)

        filas_tras_imagen = _filas_preguntas(bd_temporal, 952)
        assert len(filas_tras_imagen) == 1
        assert bytes(filas_tras_imagen[0][2]) == imagen_bytes

        # 2. El físico guarda (o corrige) un campo de texto de aspectos
        # mecánicos, en otro momento -- anular+insertar reemplaza el
        # bloque; la imagen del bloque vigente debe sobrevivir al bloque
        # NUEVO igual que sobrevivía al UPDATE parcial de antes de PR1.
        obj_texto = _pelado_preguntas()
        obj_texto.lbl_iso_mec = QLineEdit("0.85")
        obj_texto.df_lines = ["lbl_iso_mec"]
        subirlineasmensuales(obj_texto, "preguntas", 1, ref=952, usarid=False)

        filas = _filas_preguntas(bd_temporal, 952)
        assert len(filas) == 2, (
            f"esperaba la fila histórica (solo imagen) + la nueva vigente "
            f"(texto + imagen heredada): {filas}")

        vigentes = [f for f in filas if f[3] == 1]
        historicas = [f for f in filas if f[3] == 0]
        assert len(vigentes) == 1 and len(historicas) == 1, filas

        assert vigentes[0][1] == 0.85, (
            f"el campo de texto de este guardado debía quedar en el bloque "
            f"vigente: {vigentes}")
        assert bytes(vigentes[0][2]) == imagen_bytes, (
            f"la imagen del bloque vigente anterior debía sobrevivir al "
            f"reemplazo -- quedó distinta/NULL: {vigentes}")
        assert historicas[0][2] is not None and bytes(historicas[0][2]) == imagen_bytes, (
            "la fila histórica (superada) también debe conservar intacta "
            f"su propia imagen -- nunca se toca ni se borra: {historicas}")

        # 3. Un SEGUNDO resave (otra generación) debe seguir heredando la
        # imagen del bloque vigente ANTERIOR (no de la fila original de
        # crear_algo) -- prueba que la composición encadena generaciones,
        # no solo la primera.
        obj_texto2 = _pelado_preguntas()
        obj_texto2.lbl_reticulo_cent = QLineEdit("1.20")
        obj_texto2.df_lines = ["lbl_reticulo_cent"]
        subirlineasmensuales(obj_texto2, "preguntas", 1, ref=952, usarid=False)

        filas2 = _filas_preguntas(bd_temporal, 952)
        assert len(filas2) == 3
        vigentes2 = [f for f in filas2 if f[3] == 1]
        assert len(vigentes2) == 1
        assert vigentes2[0][1] == 0.85, (
            "el iso_mec del guardado anterior debía sobrevivir a esta "
            f"segunda generación también (H2.8): {vigentes2}")
        assert bytes(vigentes2[0][2]) == imagen_bytes, (
            f"la imagen debía seguir viva dos generaciones después: {vigentes2}")
