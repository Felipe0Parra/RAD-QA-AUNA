"""C.1 (PLAN_REFERENCIAS_EDITABLES_21-09.md): la pantalla de referencias.

El jefe puede cambiar un valor de referencia desde la app y la app le obliga
a decir de dónde salió; los demás pueden VER pero no fijar (R4). La pantalla
no decide el permiso -- solo pinta; lo decide el servicio (B.2) -- y no
escribe SQL.

Trampa 2: TODO `QMessageBox` (pregunta, aviso, éxito) va mockeado en cada
test de este archivo, incluidos los de éxito.
"""
import ast
import os
import pathlib
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services import referencias_qc as servicio
from ui.paginasGuia import referencias as pantalla
from ui.paginasGuia.referencias import Referencias

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SIMBOLOS_PROHIBIDOS = "✓✔✗✘✕❌✅⚠ⓘ"


class _Usuario:
    """Lo único que la pantalla lee de `user_id` (como en Usuarios)."""

    def __init__(self, usuario):
        self._usuario = usuario


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = sqlite3.connect(ruta)
    for user, fullname, rol in (("lamaya", "Luz Adriana Maya", "jefe"),
                                ("jjcastillo", "Javier Castillo", "fisico"),
                                ("superadmin", "Administrador Prueba", "admin")):
        con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
            "VALUES (?, 'x', ?, 1, '1', 'Físico Médico', ?)", (user, fullname, rol))
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture
def avisos(monkeypatch):
    """Trampa 2: los cuatro tipos mockeados. `pregunta` decide si el físico
    confirma (por defecto Sí); `mostrados` registra lo que la pantalla dijo."""
    estado = {"pregunta": QMessageBox.Yes, "mostrados": []}

    def _pregunta(*a, **k):
        estado["mostrados"].append(("question", a[2] if len(a) > 2 else ""))
        return estado["pregunta"]

    def _aviso(nombre):
        def f(*a, **k):
            estado["mostrados"].append((nombre, a[2] if len(a) > 2 else ""))
            return QMessageBox.Ok
        return f

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_pregunta))
    for nombre in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, nombre, staticmethod(_aviso(nombre)))
    return estado


def _pantalla(usuario):
    return Referencias(_Usuario(usuario))


def _rellenar(p, valor="0.627", fuente="puesta en servicio 2026",
              observaciones="medido tras el servicio técnico", equipo="Halcyon",
              energia="6mv"):
    p.cb_equipo.setCurrentText(equipo)
    p.cb_energia.setCurrentIndex(p.cb_energia.findData(energia))
    p.in_valor.setText(valor)
    p.in_fuente.setText(fuente)
    p.in_observaciones.setText(observaciones)


def _filas_bd(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT equipo, magnitud, energia, valor, fuente, observaciones, "
        "fijada_por, activo FROM referencias_qc ORDER BY id").fetchall()
    con.close()
    return filas


def _textos_tabla(tabla):
    return [[tabla.item(f, c).text() for c in range(tabla.columnCount())]
            for f in range(tabla.rowCount())]


class TestElJefeFijaYLoVe:
    def test_fijar_una_referencia_la_muestra_en_la_lista_y_en_el_historial(
            self, app, bd_temporal, avisos):
        p = _pantalla("lamaya")
        _rellenar(p)
        p._on_fijar()

        filas = _filas_bd(bd_temporal)
        assert len(filas) == 1
        assert filas[0][:7] == (
            "Halcyon", "calidad", "6mv", 0.627, "puesta en servicio 2026",
            "medido tras el servicio técnico", "Luz Adriana Maya")
        lista = _textos_tabla(p._tabla)
        assert len(lista) == 1
        assert lista[0][0] == "Halcyon" and lista[0][3] == "0.627"
        assert lista[0][5] == "puesta en servicio 2026"
        assert lista[0][7] == "Luz Adriana Maya"
        historial = _textos_tabla(p._tabla_historial)
        assert len(historial) == 1 and historial[0][0] == "Vigente"
        assert "0.627" in p.lbl_vigente.text()

    def test_cambiarla_deja_la_anterior_en_el_historial_como_reemplazada(
            self, app, bd_temporal, avisos):
        p = _pantalla("lamaya")
        _rellenar(p, valor="0.627")
        p._on_fijar()
        _rellenar(p, valor="0.640", observaciones="recalibración del 2026")
        p._on_fijar()

        assert [f[3] for f in _filas_bd(bd_temporal)] == [0.627, 0.640]
        assert len(_textos_tabla(p._tabla)) == 1  # una sola vigente
        assert _textos_tabla(p._tabla)[0][3] == "0.64"
        historial = _textos_tabla(p._tabla_historial)
        assert [h[0] for h in historial] == ["Vigente", "Reemplazada"]  # más nueva primero
        assert [h[1] for h in historial] == ["0.64", "0.627"]

    def test_pide_confirmacion_y_si_dice_que_no_no_escribe_nada(
            self, app, bd_temporal, avisos):
        avisos["pregunta"] = QMessageBox.No
        p = _pantalla("lamaya")
        _rellenar(p)
        p._on_fijar()
        assert _filas_bd(bd_temporal) == []
        assert [t for t, _ in avisos["mostrados"]] == ["question"]

    def test_la_confirmacion_avisa_que_los_controles_guardados_conservan_el_suyo(
            self, app, bd_temporal, avisos):
        p = _pantalla("lamaya")
        _rellenar(p)
        p._on_fijar()
        texto = avisos["mostrados"][0][1]
        assert "NUEVOS" in texto and "conservan" in texto

    def test_acepta_coma_decimal(self, app, bd_temporal, avisos):
        p = _pantalla("lamaya")
        _rellenar(p, valor="0,627")
        p._on_fijar()
        assert _filas_bd(bd_temporal)[0][3] == pytest.approx(0.627)

    def test_deja_el_formulario_limpio_tras_fijar(self, app, bd_temporal, avisos):
        p = _pantalla("lamaya")
        _rellenar(p)
        p._on_fijar()
        assert (p.in_valor.text(), p.in_fuente.text(), p.in_observaciones.text()) == ("", "", "")

    def test_el_administrador_tambien_puede(self, app, bd_temporal, avisos):
        p = _pantalla("superadmin")
        assert p.btn_fijar.isEnabled()
        _rellenar(p)
        p._on_fijar()
        assert _filas_bd(bd_temporal)[0][6] == "Administrador Prueba"

    def test_ix_ofrece_sus_seis_energias_y_600_y_halcyon_una(self, app, bd_temporal, avisos):
        p = _pantalla("lamaya")
        for equipo, esperado in (("Clinac ix", 6), ("Clinac 600", 1), ("Halcyon", 1)):
            p.cb_equipo.setCurrentText(equipo)
            assert p.cb_energia.count() == esperado, equipo

    def test_la_referencia_es_por_equipo_y_energia(self, app, bd_temporal, avisos):
        p = _pantalla("lamaya")
        _rellenar(p, valor="0.665", equipo="Clinac ix", energia="6mv")
        p._on_fijar()
        _rellenar(p, valor="0.627", equipo="Halcyon", energia="6mv")
        p._on_fijar()
        assert servicio.leer_referencia("Clinac ix", "calidad", "6mv")["valor"] == 0.665
        assert servicio.leer_referencia("Halcyon", "calidad", "6mv")["valor"] == 0.627
        assert servicio.leer_referencia("Clinac ix", "calidad", "15mv") is None


class TestLaAppObligaADecirDeDondeSale:
    @pytest.mark.parametrize("campo,valor", [("in_fuente", ""), ("in_fuente", "   "),
                                             ("in_observaciones", ""),
                                             ("in_observaciones", "  ")])
    def test_fuente_y_observaciones_son_obligatorias(
            self, app, bd_temporal, avisos, campo, valor):
        p = _pantalla("lamaya")
        _rellenar(p)
        getattr(p, campo).setText(valor)
        p._on_fijar()
        assert _filas_bd(bd_temporal) == []
        assert avisos["mostrados"][-1][0] == "warning"

    @pytest.mark.parametrize("valor", ["", "abc", "0", "-0.5", "nan", "inf"])
    def test_valor_invalido_no_se_guarda(self, app, bd_temporal, avisos, valor):
        p = _pantalla("lamaya")
        _rellenar(p, valor=valor)
        p._on_fijar()
        assert _filas_bd(bd_temporal) == []
        assert avisos["mostrados"][-1] == ("warning", "El valor debe ser un número mayor que cero.")


class TestLosDemasSoloVen:
    def test_un_fisico_ve_las_referencias_con_los_controles_deshabilitados(
            self, app, bd_temporal, avisos):
        jefe = _pantalla("lamaya")
        _rellenar(jefe)
        jefe._on_fijar()

        p = _pantalla("jjcastillo")
        for control in p._controles_edicion:
            assert not control.isEnabled(), control
        assert p.banda_solo_lectura.text() == pantalla.TEXTO_SOLO_LECTURA
        assert len(_textos_tabla(p._tabla)) == 1  # todos ven

    def test_un_fisico_puede_consultar_el_historial(self, app, bd_temporal, avisos):
        jefe = _pantalla("lamaya")
        _rellenar(jefe, valor="0.627")
        jefe._on_fijar()
        _rellenar(jefe, valor="0.640", observaciones="recalibración")
        jefe._on_fijar()

        p = _pantalla("jjcastillo")
        p._on_click_fila(0, 0)
        assert [h[0] for h in _textos_tabla(p._tabla_historial)] == ["Vigente", "Reemplazada"]
        assert p.cb_equipo.currentText() == "Halcyon"

    def test_invocar_fijar_a_mano_lo_rechaza_el_servicio_no_la_pantalla(
            self, app, bd_temporal, avisos):
        """Deshabilitar un botón no es un control de acceso: aunque alguien
        llame al método a mano, el servicio dice que no y deja rastro."""
        p = _pantalla("jjcastillo")
        _rellenar_directo = dict(valor="0.700", fuente="x", observaciones="y")
        p.in_valor.setText(_rellenar_directo["valor"])
        p.in_fuente.setText(_rellenar_directo["fuente"])
        p.in_observaciones.setText(_rellenar_directo["observaciones"])
        p._on_fijar()

        assert _filas_bd(bd_temporal) == []
        assert avisos["mostrados"][-1] == ("warning", "No tiene permiso para fijar referencias.")
        con = sqlite3.connect(bd_temporal)
        rastro = con.execute(
            "SELECT usuario, detalle FROM audit_log WHERE tabla='referencias_qc'").fetchall()
        con.close()
        assert rastro == [("Javier Castillo", servicio.DENEGADO_SIN_PERMISO)]

    @pytest.mark.parametrize("usuario", [None, "no_existe", ""])
    def test_sin_sesion_o_usuario_desconocido_se_trata_como_solo_lectura(
            self, app, bd_temporal, avisos, usuario):
        p = _pantalla(usuario)
        assert not p.btn_fijar.isEnabled()
        assert hasattr(p, "banda_solo_lectura")

    def test_el_jefe_no_ve_la_banda_de_solo_lectura(self, app, bd_temporal, avisos):
        assert not hasattr(_pantalla("lamaya"), "banda_solo_lectura")


class TestSeleccionYHistorial:
    def test_clic_en_una_fila_posiciona_los_combos_y_carga_su_historial(
            self, app, bd_temporal, avisos):
        p = _pantalla("lamaya")
        _rellenar(p, valor="0.665", equipo="Clinac ix", energia="15mv")
        p._on_fijar()
        _rellenar(p, valor="0.627", equipo="Halcyon", energia="6mv")
        p._on_fijar()
        # la lista está ordenada por equipo: Clinac ix primero
        p._on_click_fila(0, 0)
        assert p.cb_equipo.currentText() == "Clinac ix"
        assert p.cb_energia.currentData() == "15mv"
        assert [h[1] for h in _textos_tabla(p._tabla_historial)] == ["0.665"]

    def test_una_combinacion_sin_referencia_lo_dice_y_el_historial_queda_vacio(
            self, app, bd_temporal, avisos):
        p = _pantalla("lamaya")
        assert p._tabla_historial.rowCount() == 0
        assert "respaldo" in p.lbl_vigente.text()


class TestSinSQLYSinSimbolos:
    def test_la_pantalla_no_escribe_ni_lee_sql_solo_llama_al_servicio(self):
        fuente = (RAIZ / "ui/paginasGuia/referencias.py").read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        importados = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                importados |= {a.name for a in nodo.names}
            elif isinstance(nodo, ast.ImportFrom):
                importados.add(nodo.module)
        assert not importados & {"sqlite3", "data.ManejoDatos.conection"}
        sql = ("select ", "insert ", "update ", "delete ", "create table", "alter table")
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                assert not any(nodo.value.lower().lstrip().startswith(s) for s in sql), nodo.value
        llamadas = {n.func.attr for n in ast.walk(arbol)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == "_datos"}
        assert llamadas == {"listar_vigentes", "historial", "fijar_referencia"}

    def test_ningun_texto_lleva_simbolos_de_correcto_o_incorrecto(self):
        """DA-18: ni en las cadenas del módulo ni en lo que la pantalla
        muestra."""
        fuente = (RAIZ / "ui/paginasGuia/referencias.py").read_text(encoding="utf-8")
        for simbolo in SIMBOLOS_PROHIBIDOS:
            assert simbolo not in fuente, simbolo

    def test_los_mensajes_de_rechazo_cubren_cada_motivo_del_servicio(self):
        motivos = {servicio.DENEGADO_SIN_PERMISO, servicio.FUENTE_OBLIGATORIA,
                   servicio.OBSERVACIONES_OBLIGATORIAS, servicio.VALOR_INVALIDO}
        assert set(pantalla.MENSAJES_RECHAZO) == motivos


class TestLaListaDeMagnitudesEsCerradaYCadaUnaTieneLector:
    """Una magnitud que se pudiera fijar sin que nada la consulte sería un
    campo que miente sobre su efecto (DP-25). Se exige un lector real en
    producción para cada magnitud ofrecida."""

    def _magnitudes_leidas_en_produccion(self):
        leidas = set()
        for ruta in RAIZ.rglob("*.py"):
            rel = ruta.relative_to(RAIZ).as_posix()
            if rel.startswith(("tests/", ".venv/", "build/", "dist/",
                               "services/referencias_qc.py")):
                continue
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if (isinstance(nodo, ast.Call)
                        and getattr(nodo.func, "id", getattr(nodo.func, "attr", None))
                        == "leer_referencia" and len(nodo.args) >= 2
                        and isinstance(nodo.args[1], ast.Constant)):
                    leidas.add(nodo.args[1].value)
        return leidas

    def test_cada_magnitud_ofrecida_tiene_un_lector_en_produccion(self):
        ofrecidas = {clave for clave, _ in pantalla.MAGNITUDES}
        assert ofrecidas <= self._magnitudes_leidas_en_produccion()

    def test_las_energias_ofrecidas_son_las_que_declara_cada_pantalla_mensual(self):
        from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc
        from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        assert pantalla.ENERGIAS_POR_EQUIPO == {
            "Clinac 600": tuple(PruebaMensual600.ENERGIAS),
            "Clinac ix": tuple(PruebaMensualIX.ENERGIAS),
            "Halcyon": tuple(PruebaMensualHc.ENERGIAS),
        }
