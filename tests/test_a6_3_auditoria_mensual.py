"""A6.3 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): mensual 600/iX/Halcyon
deja rastro en `audit_log` -- equipos de medición (`subirtodo_modificado`),
cuñas/conos (`subir_control_cunas`/`guardar_control_conos`), análisis de
placa + imagen (`guardar_analisis_placa600`/`crear_algo`, mismo botón) y la
vía "optimizada" de subir tabla (`_subir_tabla_optimizada`, compartida por
600 mensual y Halcyon mensual).

El punto delicado de esta tarea (marcado "ojo" en el plan): en iX una sola
acción de usuario (`guardar_todo_ix`) dispara cuñas Y conos -- debe dejar
UNA fila de auditoría, no dos. En 600, "Guardar análisis" dispara análisis
de placa E imagen desde el mismo click (antes 2 conexiones `.clicked`
independientes) -- también debe dejar UNA fila. Los dos tests
`test_..._audita_una_sola_vez` son los que de verdad prueban el diseño;
el resto fija que cada punto simple audita como se espera.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager,
)
import ui.paginasControles.PruebasMensuales.ix_mensual as ix_mod
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    def __init__(self, nombre):
        self._nombre = nombre


def _insertar_control(ruta_bd, equipo="Clinac 600", control="Mensual", fecha="06/2026"):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, control, fecha))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


def _mensual_pelado(clase=PruebaMensual600, esIX=False):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso("Físico de Prueba")
    if esIX:
        obj.esIX = True
    return obj


class TestSubirtodoModificadoAudita:
    def _instancia(self, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO equipos (id, equip_type, model, serie, calibr_fact, "
            "fecha_calibr, activo, vigente) VALUES (13,'Cámara de ionización',"
            "'N30013','2123',0.0545,'05/02/2024',1,1)")
        con.commit()
        con.close()
        ref = _insertar_control(bd_temporal)
        obj = _mensual_pelado()
        obj.ref = ref
        combo_modelo = QComboBox()
        combo_modelo.addItems(["Seleccionar...", "N30013"])
        combo_serie = QComboBox()
        combo_serie.addItem("13 — calibrado 05/02/2024", 13)
        combo_serie.setCurrentIndex(0)
        lineedit_calib = QLineEdit("0.0545")
        obj.commenu = [combo_modelo, combo_serie, lineedit_calib]
        return obj, ref

    def test_audita_una_vez_con_el_ref_correcto(self, app, bd_temporal):
        obj, ref = self._instancia(bd_temporal)
        datos = ["N30013", obj.commenu[1].currentText(), "0.0545",
                 "", "", "", "", "", ""]
        obj.subirtodo_modificado(datos)

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "equipos_medicion", str(ref), "")]


class TestSubirControlCunasAudita:
    def _instancia(self, bd_temporal):
        ref = _insertar_control(bd_temporal)
        obj = _mensual_pelado()
        obj.ref = ref
        obj.combos_seguridad = {
            15: {"in": QPushButton(), "out": QPushButton(),
                 "right": QPushButton(), "left": QPushButton()}
        }
        for w in obj.combos_seguridad[15].values():
            w.setProperty("_texto", "Funciona")

        class _ComboFalso:
            def __init__(self, texto):
                self._texto = texto

            def currentText(self):
                return self._texto

        obj.combos_seguridad = {15: {k: _ComboFalso("Funciona") for k in
                                      ("in", "out", "right", "left")}}
        return obj, ref

    def test_600_llamada_directa_audita_una_vez(self, app, bd_temporal, monkeypatch):
        """El botón "Subir" de cuñas en 600 llama subir_control_cunas
        directo (auditar=True por defecto) -- 1 fila."""
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        obj, ref = self._instancia(bd_temporal)
        obj.subir_control_cunas(obj.combos_seguridad)

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "control_cunas", str(ref), "")]

    def test_auditar_false_no_deja_rastro(self, app, bd_temporal, monkeypatch):
        """El caso que usa guardar_todo_ix (iX) -- subir_control_cunas por
        sí sola NO debe auditar cuando se le pide explícitamente."""
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        obj, ref = self._instancia(bd_temporal)
        obj.subir_control_cunas(obj.combos_seguridad, auditar=False)

        assert _audit_log(bd_temporal) == []


class TestGuardarTodoIxAuditaUnaSolaVez:
    """El caso "ojo" del plan: cuñas + conos, mismo click en iX -- 1 fila,
    no 2.

    A2 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase A, R1) reescribió
    `guardar_todo_ix` sobre T3 (PLAN_CONOS_MENSUAL_12-08.md §4-T3): ya no
    hay un "guardado parcial" que auditar con detalle distinto -- la
    validación de faltantes (`_filas_y_faltantes_conos`/`_faltantes_cunas`)
    corre ANTES de escribir nada, y si algo falta, NINGUNA de las dos
    tablas se toca ni se audita. El spy mockea esas dos funciones de
    detección (no los botones/combos reales, que este objeto pelado no
    tiene) para controlar el escenario sin reconstruir toda la UI."""

    def _instancia(self, bd_temporal, monkeypatch, todo_completo=True):
        monkeypatch.setattr(mensual_mod.QMessageBox, "warning", lambda *a, **k: None)
        monkeypatch.setattr(mensual_mod.QMessageBox, "information", lambda *a, **k: None)
        ref = _insertar_control(bd_temporal, equipo="Clinac ix")
        obj = _mensual_pelado(clase=PruebaMensualIX, esIX=True)
        obj.ref = ref
        obj.combos_seguridad = {15: {}}  # solo necesita ser truthy (hay_cunas)
        obj.df_seg_line = None

        llamadas = []

        if todo_completo:
            obj._filas_y_faltantes_conos = lambda: (
                llamadas.append(("_filas_y_faltantes_conos", None)) or
                ([("6x6", 1)], []))
        else:
            obj._filas_y_faltantes_conos = lambda: (
                llamadas.append(("_filas_y_faltantes_conos", None)) or
                ([], ["6x6"]))
        obj._faltantes_cunas = lambda combos: (
            llamadas.append(("_faltantes_cunas", None)) or [])

        def _subir_control_cunas_spy(combos_seguridad, df_lines=None,
                                     auditar=True, mostrar_mensaje=True):
            llamadas.append(("subir_control_cunas", auditar))

        def _guardar_control_conos_spy():
            llamadas.append(("guardar_control_conos", None))
            return True

        obj.subir_control_cunas = _subir_control_cunas_spy
        obj.guardar_control_conos = _guardar_control_conos_spy
        return obj, ref, llamadas

    def test_ambas_escrituras_se_disparan_pero_solo_una_fila_de_auditoria(
            self, app, bd_temporal, monkeypatch):
        obj, ref, llamadas = self._instancia(bd_temporal, monkeypatch, todo_completo=True)
        obj.guardar_todo_ix()

        # Las dos escrituras SÍ ocurrieron...
        assert ("subir_control_cunas", False) in llamadas
        assert ("guardar_control_conos", None) in llamadas
        # ...pero auditar=False evita que subir_control_cunas audite por su
        # cuenta, y guardar_control_conos no audita nunca por sí misma.
        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        # M4 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §M4): la fila única
        # ya no nombra la tabla inventada "control_cunas_y_conos" -- usa
        # "control_cunas" (tabla real) y el detalle nombra las dos.
        assert filas[0][:4] == ("Físico de Prueba", "guardar",
                                "control_cunas", str(ref))
        assert filas[0][4] == "cuñas + conos (mensual iX)"

    def test_conos_incompletos_no_escribe_nada_ni_audita(
            self, app, bd_temporal, monkeypatch):
        """A2: si la validación previa encuentra conos incompletos, NI
        `subir_control_cunas` NI `guardar_control_conos` se llaman -- el
        guardado se bloquea entero, y por tanto no hay nada que auditar."""
        obj, ref, llamadas = self._instancia(bd_temporal, monkeypatch, todo_completo=False)
        obj.guardar_todo_ix()

        assert ("subir_control_cunas", False) not in llamadas
        assert not any(nombre == "guardar_control_conos" for nombre, _ in llamadas)
        filas = _audit_log(bd_temporal)
        assert filas == []


class TestGuardarAnalisisEImagenAuditaUnaSolaVez:
    """El otro caso "1 fila, no 2": "Guardar análisis" disparaba 2
    conexiones .clicked independientes (placa + imagen) -- ahora es 1
    handler, 1 fila."""

    def _instancia(self, bd_temporal, monkeypatch, valores_ok=True):
        """IM5 (Fase 6): los dobles devuelven ahora un valor con significado
        -- `guardar_analsis` dice si los valores calculados se guardaron, y
        `dbImagen` devuelve `(nombre, bytes)` de la imagen. Antes eran
        `lambda: llamadas.append(...)`, que devuelve `None`: con el contrato
        nuevo eso significa "falló", y el test entraba en la rama de fallo
        (y se colgaba en un QMessageBox sin mockear -- trampa 2)."""
        ref = _insertar_control(bd_temporal)
        obj = _mensual_pelado()
        obj.ref = ref
        obj.res = {}
        obj.imagen_path = "no-importa.jpg"

        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            lambda *a, **k: None)
        monkeypatch.setattr(mensual_mod.QMessageBox, "warning",
                            lambda *a, **k: None)

        llamadas = []

        def _guardar_analsis():
            llamadas.append("guardar_analsis")
            return valores_ok

        def _db_imagen(ref_, imagen):
            llamadas.append(("dbImagen", ref_, imagen))
            return ("no-importa.jpg", 123)

        obj.guardar_analsis = _guardar_analsis
        obj.dbImagen = _db_imagen
        return obj, ref, llamadas

    def test_ambas_acciones_se_disparan_con_una_sola_fila(
            self, app, bd_temporal, monkeypatch):
        obj, ref, llamadas = self._instancia(bd_temporal, monkeypatch)
        obj.guardar_analisis_e_imagen()

        assert "guardar_analsis" in llamadas
        assert ("dbImagen", ref, "no-importa.jpg") in llamadas
        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        assert filas[0][:4] == ("Físico de Prueba", "guardar",
                                "analisis_placa600", str(ref))

    def test_si_los_valores_no_se_guardan_la_imagen_tampoco(
            self, app, bd_temporal, monkeypatch):
        """IM5: la imagen y sus valores calculados son un solo dato -- o
        entran los dos o ninguno. Antes, `guardar_analisis_placa600` se
        tragaba su excepción y esta función seguía adelante guardando la
        imagen igual, dejándola huérfana (`ref=1` y `ref=5` de producción:
        imagen presente, 0 filas en `analisis_placa_*`)."""
        obj, ref, llamadas = self._instancia(
            bd_temporal, monkeypatch, valores_ok=False)
        obj.guardar_analisis_e_imagen()

        assert "guardar_analsis" in llamadas
        assert not any(c[0] == "dbImagen" for c in llamadas if isinstance(c, tuple)), (
            "la imagen NO debe guardarse si sus valores calculados fallaron")

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1, "el intento fallido también deja rastro"
        assert "fallido" in filas[0][4], (
            f"la auditoría debe decir que no se guardó nada: {filas[0]}")


class TestSubirTablaOptimizadaAudita:
    def test_audita_con_la_tabla_y_ref_correctos(self, app, bd_temporal, monkeypatch):
        ref = _insertar_control(bd_temporal)
        obj = _mensual_pelado()
        obj.ref = ref
        obj.anual = False

        # B1 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase B): el fake ahora
        # devuelve True (guardado exitoso) -- con el `None` que tenía antes,
        # el `if not resultado` nuevo de _subir_tabla_optimizada dispara un
        # QMessageBox.critical sin mockear (Trampa 2, cuelga la suite).
        monkeypatch.setattr(mensual_mod, "loadtablacomplex", lambda *a, **k: True)
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(mensual_mod.QMessageBox, "critical",
                            staticmethod(lambda *a, **k: None))

        table = object()  # loadtablacomplex está parcheado -- no se usa de verdad
        obj._subir_tabla_optimizada(table, "indicadores_brazo", ref)

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "indicadores_brazo", str(ref), "")]

    def test_guardado_fallido_no_audita_y_avisa(self, app, bd_temporal, monkeypatch):
        """B1: si loadtablacomplex falla, no se audita un guardado que no
        ocurrió, y el físico se entera (antes: silencio total, H3)."""
        ref = _insertar_control(bd_temporal)
        obj = _mensual_pelado()
        obj.ref = ref
        obj.anual = False

        monkeypatch.setattr(mensual_mod, "loadtablacomplex", lambda *a, **k: False)
        avisos = []
        monkeypatch.setattr(mensual_mod.QMessageBox, "critical",
                            staticmethod(lambda *a, **k: avisos.append(a[1:])))

        table = object()
        obj._subir_tabla_optimizada(table, "indicadores_brazo", ref)

        assert len(avisos) == 1
        assert _audit_log(bd_temporal) == []
