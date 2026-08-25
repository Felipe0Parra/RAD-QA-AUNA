"""RP1+RP2+RP3 (PLAN_LECTURA_VIGENTE_18-08.md §6): reparación de los 3
sitios reales de lectura sin filtro de `activo` que el rebuild del 18-08
destapó -- verificados contra la FORMA EXACTA de los datos reales
encontrados en `BaseDatosQA(Rebuild_18-8-2026).db` (refs 43/19/952), no
casos inventados.

Cada clase reproduce el rojo-antes-que-verde de su tarea: la forma exacta
del defecto medido en la BD real, con el número de filas y el valor
esperado tomados directamente de esa medición.
"""
import os
import sqlite3
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QTableWidget, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import mostrar_controles_mensuales, crear_algo
import data.ManejoDatos.Tablas_Anuales.tablas_anuales as tablas_anuales_mod
from data.ManejoDatos.Tablas_Anuales.tablas_anuales import mostrar_tabla_equipos_anual


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + migraciones reales
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sin_avisos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


def _crear_control(ruta_bd, control_id, equipo="Clinac ix", fecha="18/08/2026"):
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, ?, 'Mensual', ?, 'Físico de Prueba')",
        (control_id, equipo, fecha))
    con.commit()
    con.close()


def _crear_control_anual(ruta_bd, control_id, equipo="Clinac ix", fecha="02/2026"):
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, ?, 'Anual', ?, 'Físico de Prueba')",
        (control_id, equipo, fecha))
    con.commit()
    con.close()


class TestRP1ControlMensualYDosisDeReferencia:
    """Forma EXACTA del ref=43 real (rebuild 18-08-2026): 2 filas de
    `preguntas` (1 histórica, 1 vigente) y 4 de `dosimetriaMen` en '6mv'
    (rowid 45/51 dosis=None activo=0, rowid 57 dosis=1.0125 activo=0,
    rowid 63 dosis=1.0125 activo=1 -- la vigente). Antes del fix: 2 filas
    en pantalla y `LIMIT 1` sin `ORDER BY` devolvía la primera por rowid
    (dosis=None) en vez de la vigente."""

    def _sembrar(self, ruta_bd, ref):
        con = sqlite3.connect(ruta_bd)
        # preguntas: 1 histórica + 1 vigente (mismo patrón que un resave de
        # texto tras PR1 -- anular+insertar, nunca DELETE)
        con.execute(
            "INSERT INTO preguntas (ref, iso_mec, activo) VALUES (?, 1.0, 0)", (ref,))
        con.execute(
            "INSERT INTO preguntas (ref, iso_mec, activo) VALUES (?, 1.0, 1)", (ref,))
        # dosimetriaMen: 4 generaciones en 6mv, rowid ascendente = orden de
        # inserción real observado (45, 51, 57, 63)
        for dosis, activo in [(None, 0), (None, 0), (1.0125, 0), (1.0125, 1)]:
            con.execute(
                "INSERT INTO dosimetriaMen (ref, energia, dosis_ref_cgy_um, activo) "
                "VALUES (?, '6mv', ?, ?)", (ref, dosis, activo))
        con.commit()
        con.close()

    def test_no_aparece_duplicado_en_pantalla(self, app, bd_temporal):
        _crear_control(bd_temporal, 43)
        self._sembrar(bd_temporal, 43)

        tabla = QTableWidget()
        mostrar_controles_mensuales(None, tabla, equipo_filtrar="Clinac ix")

        assert tabla.rowCount() == 1, (
            f"el control 43 debía aparecer UNA sola vez -- antes del fix el "
            f"LEFT JOIN a preguntas sin filtro de activo lo duplicaba por "
            f"cada versión de preguntas: {tabla.rowCount()} filas")

    def test_la_subconsulta_de_dosis_resuelve_la_vigente_no_una_arbitraria(
            self, bd_temporal):
        """Verificación independiente (no reejecuta el SQL de producción,
        para no autoconfirmarse -- mismo criterio que el ancla de CL2): la
        fila vigente de dosimetriaMen para (ref, energia) es la que tiene
        activo=1; comprobamos que existe y su dosis es 1.0125, y que la
        query de mostrar_controles_mensuales -- ejercitada vía la función
        real -- no puede haber tomado ninguna otra (los datos sembrados
        garantizan que rowid=45, la primera por LIMIT-sin-filtro, tiene
        dosis=None)."""
        _crear_control(bd_temporal, 43)
        self._sembrar(bd_temporal, 43)

        con = sqlite3.connect(bd_temporal)
        vigente = con.execute(
            "SELECT dosis_ref_cgy_um FROM dosimetriaMen "
            "WHERE ref = 43 AND energia = '6mv' AND activo = 1").fetchone()
        primera_por_rowid = con.execute(
            "SELECT dosis_ref_cgy_um FROM dosimetriaMen "
            "WHERE ref = 43 AND energia = '6mv' ORDER BY rowid LIMIT 1").fetchone()
        con.close()

        assert vigente == (1.0125,)
        assert primera_por_rowid == (None,), (
            "el dato sembrado debe reproducir el defecto real: la primera "
            "fila por rowid es justo la que NO es la vigente")

        # La función real, sin excepción y sin fila vacía en la posición
        # "Imagen" (col 20) que solo se marca vacía cuando dosis_ref_cgy_um
        # resolvió a None -- prueba indirecta de que el subquery corregido
        # alcanzó la fila vigente, no la primera por rowid.
        tabla = QTableWidget()
        mostrar_controles_mensuales(None, tabla, equipo_filtrar="Clinac ix")
        assert tabla.rowCount() == 1
        celda = tabla.item(0, 20)
        assert celda is not None and celda.text() == "Imagen Cargada", (
            f"col 20 se deriva de dosis_ref_cgy_um -- vacía indicaría que "
            f"la subconsulta resolvió a None (rowid=45) en vez de a la "
            f"vigente (rowid=63, dosis=1.0125): texto={celda and celda.text()!r}")


class TestRP2EquiposAnualSoloMuestraLoVigente:
    """Forma EXACTA del ref=19 real: 8 filas de equipos_medicion, 4
    históricas (activo=0) + 4 vigentes (activo=1) -- antes del fix se
    mostraban las 8 mezcladas."""

    def _sembrar(self, ruta_bd, ref):
        con = sqlite3.connect(ruta_bd)
        historicas = [
            ("Principal Fotones", "N31010", "1825"),
            ("Principal Electrones", "N34001", "1069"),
            ("Secundaria", "N31022", "152342"),
            ("Electrómetro", "CDX-2000B", "B091982"),
        ]
        vigentes = [
            ("Principal Fotones", "N31022", "152342"),
            ("Principal Electrones", "N34001", "1069"),
            ("Secundaria", "N31022", "152342"),
            ("Electrómetro", "CDX-2000B", "B091982"),
        ]
        for tipo, modelo, serie in historicas:
            con.execute(
                "INSERT INTO equipos_medicion (ref, tipo_camara, model, serie, activo) "
                "VALUES (?, ?, ?, ?, 0)", (ref, tipo, modelo, serie))
        for tipo, modelo, serie in vigentes:
            con.execute(
                "INSERT INTO equipos_medicion (ref, tipo_camara, model, serie, activo) "
                "VALUES (?, ?, ?, ?, 1)", (ref, tipo, modelo, serie))
        con.commit()
        con.close()

    def test_solo_se_ven_las_4_filas_vigentes(self, app, bd_temporal, monkeypatch):
        _crear_control_anual(bd_temporal, 19)
        self._sembrar(bd_temporal, 19)

        capturado = {}

        def _capturar_dialogo(parent, headers, data, w, h, tabla_db, id_ref):
            capturado["data"] = data

        monkeypatch.setattr(tablas_anuales_mod, "_mostrar_dialogo_anual", _capturar_dialogo)

        mostrar_tabla_equipos_anual(None, 19)

        data = capturado["data"]
        assert len(data) == 4, (
            f"debían verse solo las 4 filas vigentes, no las 8 (4 "
            f"históricas + 4 vigentes): {data}")
        series = {fila[3] for fila in data}  # (tipo_camara, equip_type, model, serie)
        assert series == {"152342", "1069", "B091982"}, (
            f"las series mostradas deben ser las VIGENTES (N31010/1825 es "
            f"histórica y no debe aparecer): {series}")


class TestRP3ImagenNoSeReescribeEnFilasAnuladas:
    """crear_algo: la imagen nueva debe tocar SOLO el bloque vigente -- antes
    de RP3, el UPDATE sin filtro escribía la imagen nueva en TODAS las filas
    del ref, incluidas las anuladas, reescribiendo un snapshot histórico que
    debía quedar fijo.

    IM1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IM1, Fase 6, 25-08) cambió el
    MECANISMO sin tocar esa garantía: `crear_algo` ya no hace `UPDATE` en
    sitio, compone un bloque nuevo y lo reemplaza con `reemplazar_bloque`
    (EB1). Lo que cambia aquí es el CONTEO de filas -- cada guardado de
    imagen deja ahora su propia generación anulada en vez de pisar la
    vigente, así que tras dos imágenes hay 3 filas donde antes había 2. La
    afirmación de fondo es la misma y sigue siendo la que importa: **ninguna
    fila anulada lleva jamás la imagen nueva**."""

    def _pelado(self):
        obj = QWidget.__new__(QWidget)
        QWidget.__init__(obj)
        return obj

    def test_la_fila_anulada_conserva_su_propia_imagen(
            self, app, bd_temporal, monkeypatch, tmp_path):
        _sin_avisos(monkeypatch)
        _crear_control(bd_temporal, 952)

        imagen1 = tmp_path / "imagen1.png"
        imagen1.write_bytes(b"contenido de la PRIMERA imagen")
        imagen2 = tmp_path / "imagen2.png"
        imagen2.write_bytes(b"contenido de la SEGUNDA imagen, distinta")

        # 1. Sube la primera imagen (INSERT, no hay fila previa)
        obj1 = self._pelado()
        obj1.imagen_path = str(imagen1)
        crear_algo(obj1, 952, None)

        # 2. Guardar texto de aspectos mecánicos anula+inserta -- deja una
        # fila histórica (con imagen1) y una vigente (hereda imagen1 por
        # PR1). Se simula directamente para no depender de widgets reales.
        con = sqlite3.connect(bd_temporal)
        con.execute("UPDATE preguntas SET activo = 0 WHERE ref = 952 AND activo = 1")
        con.execute(
            "INSERT INTO preguntas (ref, iso_mec, imagen, activo) "
            "SELECT ref, 0.85, imagen, 1 FROM preguntas WHERE ref = 952 AND activo = 0")
        con.commit()
        con.close()

        # 3. Sube una SEGUNDA imagen -- debe quedar SOLO en el bloque
        # vigente nuevo. Antes de RP3 (UPDATE sin filtro de activo) habría
        # escrito imagen2 en TODAS las filas del ref.
        obj2 = self._pelado()
        obj2.imagen_path = str(imagen2)
        crear_algo(obj2, 952, None)

        con = sqlite3.connect(bd_temporal)
        filas = con.execute(
            "SELECT activo, imagen FROM preguntas WHERE ref = 952 ORDER BY rowid").fetchall()
        con.close()

        # IM1: 3 filas, no 2 -- la primera anulada en el paso 2, la segunda
        # anulada por el propio `crear_algo` de este paso, y la vigente
        # nueva. Antes de IM1 el guardado de la imagen pisaba la vigente en
        # sitio y no dejaba generación.
        assert len(filas) == 3, filas
        historicas = [f for f in filas if f[0] == 0]
        vigente = [f for f in filas if f[0] == 1]
        assert len(historicas) == 2 and len(vigente) == 1, filas

        for h in historicas:
            assert bytes(h[1]) == b"contenido de la PRIMERA imagen", (
                "cada fila histórica (superada) debía conservar SU propia "
                "imagen -- si esto falla, el guardado de la imagen volvió a "
                "escribir sobre filas anuladas")
        assert bytes(vigente[0][1]) == b"contenido de la SEGUNDA imagen, distinta", (
            "el bloque vigente sí debe llevar la imagen nueva")
