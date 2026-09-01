"""A1 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §A1): al reproducir el
"bloqueo" del formulario ANUAL del iX aparecieron dos defectos reales -- no
había ninguna puerta que impidiera guardar; lo que pasaba es que cada
guardado BORRABA el trabajo anterior y la relectura lo mostraba corrido.

1. `loadtablacomplex` (load.py) borraba con `DELETE ... WHERE ref=?` a
   secas, sin acotar por `id_energia` ni `tam_pdd`. El iX tiene 6 energías,
   cada una con su propio botón "Subir": subir 15 MV borraba lo ya guardado
   de 6 MV. Y en `tabla_factores_sobre_eje` ni siquiera sobrevivía UN clic
   -- `guardar_todas_fse` llama una vez por cada tamaño de PDD dentro del
   MISMO clic, y cada llamada borraba lo que las anteriores acababan de
   escribir.

2. `_llenar_tabla_bd` (seiscientos_mensual.py) recortaba un prefijo fijo de
   3 columnas al releer una tabla anual. `tabla_factores_sobre_eje` tiene
   CUATRO identificadoras (id, ref, id_energia, tam_pdd), así que `tam_pdd`
   se colaba en la primera columna de la vista y corría todas las demás una
   posición; volver a pulsar "Subir" persistía esa corrupción.

Contrato único de las dos mitades: lo que un "Subir" borra es exactamente el
bloque que vuelve a escribir (`columnas_identificadoras`, load.py), y lo que
se relee vuelve a la misma columna de la que salió.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import (QApplication, QPushButton, QTableWidgetItem,
                             QToolBox, QWidget)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import columnas_identificadoras
from services.db_pool import DatabaseManager
import ui.paginasControles.PruebasAnuales.ix_anual as ix_anual_mod
from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    # A2 (PLAN_REPARACION_ANUAL_27-08.md §Fase 4, AN-7): guardar_todas_fse
    # ahora SÍ muestra un QMessageBox.information en el camino de éxito
    # (antes solo imprimía en consola) -- este archivo pulsa "Subir" de
    # verdad (_pulsar_subir), muchas veces, sobre una BD real. Sin
    # mockear esto, cada click de éxito dispararía un diálogo modal real
    # bajo QT_QPA_PLATFORM=offscreen (Trampa 2: cuelga la suite entera,
    # no lanza ninguna excepción).
    monkeypatch.setattr(ix_anual_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(ix_anual_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


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
    _nombre = "Físico de Prueba"


def _insertar_control(ruta_bd, fecha="06/2026"):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES ('Clinac ix', 'Anual', ?)",
        (fecha,))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _anual_ix(ref):
    """Formulario anual de iX pelado, con sus 4 grupos de tablas creados de
    verdad por `_crear_tablas_pruebas` (6 energías, y 3 tablas PDD dentro de
    cada energía para el factor sobre el eje)."""
    obj = PruebaAnualIX.__new__(PruebaAnualIX)
    QWidget.__init__(obj)
    obj.anual = True
    obj.esIX = True
    obj.equipo_f = "Clinac ix"
    obj.ref = ref
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    obj.subtool = QToolBox()
    obj.subtool2 = QToolBox()
    obj.subtool3 = QToolBox()
    obj.subtool4 = QToolBox()
    obj._crear_tablas_pruebas()
    return obj


def _rellenar(tabla, valores):
    for f, fila in enumerate(valores):
        for c, valor in enumerate(fila):
            tabla.setItem(f, c, QTableWidgetItem(str(valor)))


def _pulsar_subir(tabla):
    """Pulsa el botón "Subir" que cuelga de esa tabla -- el mismo camino que
    recorre el físico, no una llamada directa a loadtablacomplex."""
    botones = tabla.parentWidget().findChildren(QPushButton)
    assert botones, "esa tabla no tiene botón Subir"
    botones[0].click()


def _filas(ruta_bd, tabla_bd, ref):
    """Filas VIGENTES -- lo que el físico ve. CT2
    (PLAN_CONTRATO_GUARDADO_13-08.md §6-CT2): desde que loadtablacomplex
    anula en vez de borrar, un reguardado deja también la fila anulada en
    la tabla; sin este filtro estas pruebas verían el histórico acumulado,
    no el estado vigente que es lo que en verdad prueban."""
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        f"SELECT * FROM {tabla_bd} WHERE ref = ? "
        f"AND (activo IS NULL OR activo = 1) ORDER BY id", (ref,)).fetchall()
    con.close()
    return filas


def _vista(tabla):
    return [[tabla.item(f, c).text() if tabla.item(f, c) else None
             for c in range(tabla.columnCount())]
            for f in range(tabla.rowCount())]


# --------------------------------------------------------------------------
# Defecto 1 -- el DELETE arrasaba con todo el control, no con el bloque
# --------------------------------------------------------------------------

class TestGuardarUnaEnergiaNoBorraLasOtras:
    """Las 3 tablas anuales con `id_energia` y sin `tam_pdd`. El iX tiene un
    botón "Subir" por energía: usar el de 15 MV no puede tocar lo que el
    físico ya guardó en 6 MV."""

    @pytest.mark.parametrize("tabla_bd,grupo,valores_6mv,valores_15mv", [
        ("tabla_factor_campo", "tablas_fc",
         [["3x3", 0.90, 0.90, 0.0], ["10x10", 1.00, 1.00, 0.0]],
         [["3x3", 0.80, 0.80, 0.0], ["10x10", 1.10, 1.10, 0.0]]),
        ("tabla_factores_transmision", "tablas_fta",
         [["15", 0.55, 0.55, 0.0], ["30", 0.44, 0.44, 0.0]],
         [["15", 0.66, 0.66, 0.0], ["30", 0.33, 0.33, 0.0]]),
        ("tabla_control_camaras_monitoras", "tablas_ccm",
         [["Fac. Calibración", 1.11], ["Reproducibilidad", 2.22]],
         [["Fac. Calibración", 3.33], ["Reproducibilidad", 4.44]]),
    ])
    def test_las_dos_energias_sobreviven(self, app, bd_temporal, tabla_bd, grupo,
                                         valores_6mv, valores_15mv):
        ref = _insertar_control(bd_temporal)
        obj = _anual_ix(ref)
        tablas = getattr(obj, grupo)

        _rellenar(tablas[0]["tabla"], valores_6mv)    # 6 MV  -> id_energia 0
        _pulsar_subir(tablas[0]["tabla"])
        _rellenar(tablas[1]["tabla"], valores_15mv)   # 15 MV -> id_energia 1
        _pulsar_subir(tablas[1]["tabla"])

        energias = sorted({fila[2] for fila in _filas(bd_temporal, tabla_bd, ref)})
        assert energias == [0, 1], (
            f"subir 15 MV borró lo guardado de 6 MV en {tabla_bd}: el DELETE "
            "no está acotado por id_energia")

    def test_las_seis_energias_del_ix_sobreviven_en_secuencia(self, app, bd_temporal):
        """El caso real: el físico recorre las 6 energías del iX pulsando
        "Subir" en cada una."""
        ref = _insertar_control(bd_temporal)
        obj = _anual_ix(ref)

        for id_energia, entry in enumerate(obj.tablas_fc):
            _rellenar(entry["tabla"], [["3x3", 0.90 + id_energia, 0.90, 0.0]])
            _pulsar_subir(entry["tabla"])

        filas = _filas(bd_temporal, "tabla_factor_campo", ref)
        assert sorted({fila[2] for fila in filas}) == [0, 1, 2, 3, 4, 5], (
            "de las 6 energías del iX solo sobrevivió la última guardada")
        # cada energía conserva SU valor, no el de la última guardada
        medidos = {fila[2]: fila[4] for fila in filas if fila[3] == "3x3"}
        assert medidos == {i: 0.90 + i for i in range(6)}

    def test_reguardar_la_misma_energia_reemplaza_su_bloque_sin_duplicar(
            self, app, bd_temporal):
        """El contrato de reemplazo que ya existía no se pierde al acotar:
        corregir un dato mal tecleado y volver a subir deja UN bloque."""
        ref = _insertar_control(bd_temporal)
        obj = _anual_ix(ref)
        tabla = obj.tablas_fc[0]["tabla"]

        _rellenar(tabla, [["3x3", 0.90, 0.90, 0.0]])
        _pulsar_subir(tabla)
        _rellenar(tabla, [["3x3", 0.95, 0.95, 0.0]])  # el físico corrige
        _pulsar_subir(tabla)

        filas = [f for f in _filas(bd_temporal, "tabla_factor_campo", ref)
                 if f[3] == "3x3"]
        assert len(filas) == 1, "el reguardado acumuló en vez de reemplazar (vigente)"
        assert filas[0][4] == 0.95, "quedó el valor viejo, no el corregido"

        # CT2: el valor viejo no se borró -- quedó anulado (DA-03), no
        # perdido. El histórico completo tiene las 2 filas.
        con = sqlite3.connect(bd_temporal)
        historico = con.execute(
            "SELECT factor_campo, activo FROM tabla_factor_campo "
            "WHERE ref = ? AND tamano_campo = '3x3'", (ref,)).fetchall()
        con.close()
        assert sorted(historico) == [(0.9, 0), (0.95, 1)], (
            "el valor corregido debía quedar histórico (activo=0), no "
            f"perdido: {historico}")


class TestUnSoloClicGuardaLasTresTablasPDD:
    """`tabla_factores_sobre_eje` es la única con `tam_pdd`: dentro de cada
    energía hay 3 tablas (10x10, 15x15, 20x20) y un único botón "Subir", que
    las sube las tres en bucle."""

    def test_las_9_filas_de_una_energia_sobreviven_al_mismo_clic(
            self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        obj = _anual_ix(ref)

        for entry in obj.tablas_fse[0]:               # 6 MV, sus 3 PDD
            _rellenar(entry["tabla"],
                      [[5, 1.0, 1.0, 0.0], [10, 2.0, 2.0, 0.0], [15, 3.0, 3.0, 0.0]])
        _pulsar_subir(obj.tablas_fse[0][-1]["tabla"])  # el único botón

        filas = _filas(bd_temporal, "tabla_factores_sobre_eje", ref)
        assert sorted({fila[3] for fila in filas}) == [
            "PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"], (
            "el bucle de guardar_todas_fse borró las PDD que él mismo acababa "
            "de escribir -- solo sobrevivió la última del bucle")
        assert len(filas) == 9, "3 tamaños de PDD x 3 profundidades"

    def test_guardar_otra_energia_no_borra_las_pdd_de_la_primera(
            self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        obj = _anual_ix(ref)

        for id_energia in (0, 1):
            for entry in obj.tablas_fse[id_energia]:
                _rellenar(entry["tabla"], [[5, 1.0, 1.0, 0.0]])
            _pulsar_subir(obj.tablas_fse[id_energia][-1]["tabla"])

        filas = _filas(bd_temporal, "tabla_factores_sobre_eje", ref)
        bloques = sorted({(fila[2], fila[3]) for fila in filas})
        assert len(bloques) == 6, (
            "2 energías x 3 tamaños de PDD = 6 bloques; se perdió alguno")


# --------------------------------------------------------------------------
# Defecto 2 -- la relectura corría las columnas una posición
# --------------------------------------------------------------------------

class TestReabrirUnControlNoDesplazaLasColumnas:

    def _guardar_fse_6mv(self, ruta_bd):
        ref = _insertar_control(ruta_bd)
        obj = _anual_ix(ref)
        for entry in obj.tablas_fse[0]:
            _rellenar(entry["tabla"],
                      [[5, 1.0, 1.1, 0.1], [10, 2.0, 2.2, 0.2], [15, 3.0, 3.3, 0.3]])
        _pulsar_subir(obj.tablas_fse[0][-1]["tabla"])
        return ref

    def test_factores_sobre_eje_vuelve_a_la_columna_de_la_que_salio(
            self, app, bd_temporal):
        """La tabla con `tam_pdd`: "Profundidad (cm)" debe mostrar 5, no el
        texto 'PPD (20 x 20)'."""
        ref = self._guardar_fse_6mv(bd_temporal)

        reabierto = _anual_ix(ref)                    # el físico reabre el control
        tabla = reabierto.tablas_fse[0][-1]["tabla"]  # PPD (20 x 20)

        assert _vista(tabla) == [
            ["5", "1.0", "1.1", "0.1"],
            ["10", "2.0", "2.2", "0.2"],
            ["15", "3.0", "3.3", "0.3"],
        ], ("las columnas quedaron corridas una posición: tam_pdd se coló en "
            "la primera columna de la vista")

    def test_reabrir_y_volver_a_subir_no_corrompe_lo_guardado(
            self, app, bd_temporal):
        """Si la vista viene corrida, pulsar "Subir" sobre ella persiste la
        corrupción (y la agrava: el tam_pdd acaba duplicado dentro de la
        propia fila). Reabrir y reguardar sin tocar nada debe ser inocuo."""
        ref = self._guardar_fse_6mv(bd_temporal)
        antes = _filas(bd_temporal, "tabla_factores_sobre_eje", ref)

        reabierto = _anual_ix(ref)
        _pulsar_subir(reabierto.tablas_fse[0][-1]["tabla"])
        despues = _filas(bd_temporal, "tabla_factores_sobre_eje", ref)

        # se comparan los datos, no los id (el reemplazo los renumera)
        assert [fila[1:] for fila in despues] == [fila[1:] for fila in antes], (
            "reabrir y volver a subir sin tocar nada alteró los datos")

    def test_una_tabla_anual_sin_tam_pdd_se_sigue_releyendo_bien(
            self, app, bd_temporal):
        """Anti-regresión: el recorte de 3 era correcto para las tablas con
        `[id, ref, id_energia]` y debe seguir siéndolo."""
        ref = _insertar_control(bd_temporal)
        obj = _anual_ix(ref)
        _rellenar(obj.tablas_fc[1]["tabla"], [["3x3", 0.80, 0.85, 0.5]])
        _pulsar_subir(obj.tablas_fc[1]["tabla"])

        reabierto = _anual_ix(ref)
        assert _vista(reabierto.tablas_fc[1]["tabla"])[0] == \
            ["3x3", "0.8", "0.85", "0.5"]


# --------------------------------------------------------------------------
# La fuente única que comparten las dos mitades
# --------------------------------------------------------------------------

class TestColumnasIdentificadoras:

    @pytest.mark.parametrize("tabla_bd,esperado", [
        ("tabla_factor_campo", ("id", "ref", "id_energia")),
        ("tabla_factores_transmision", ("id", "ref", "id_energia")),
        ("tabla_control_camaras_monitoras", ("id", "ref", "id_energia")),
        # la única con un cuarto identificador
        ("tabla_factores_sobre_eje", ("id", "ref", "id_energia", "tam_pdd")),
    ])
    def test_prefijo_leido_del_esquema(self, bd_temporal, tabla_bd, esperado):
        assert columnas_identificadoras(tabla_bd) == esperado

    @pytest.mark.parametrize("tabla_bd,esperado", [
        # sin id_energia: el prefijo corta en la primera columna de datos
        ("control_cunas", ("id", "ref")),
        # sin `id` siquiera: el prefijo no da por supuesta ninguna columna
        ("tamano_campo", ("ref",)),
    ])
    def test_el_prefijo_corta_en_la_primera_columna_de_datos(
            self, bd_temporal, tabla_bd, esperado):
        assert columnas_identificadoras(tabla_bd) == esperado

    def test_tabla_inexistente_no_revienta(self, bd_temporal):
        assert columnas_identificadoras("tabla_que_no_existe") == ()
