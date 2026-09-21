"""B.4 (PLAN_REFERENCIAS_EDITABLES_21-09.md): `dosimetriaMen.origen_referencia`
dice de dónde salió el número contra el que se juzgó cada energía:
  - 'tabla'    llegó precargado desde `referencias_qc` (B.3) y no se tocó;
  - 'manual'   el físico lo tecleó o lo cambió ese día;
  - 'respaldo' el widget estaba vacío y se guardó el respaldo por energía (A.2);
  - NULL       fila histórica: no se sabe, y no se inventa.

Es solo TRAZABILIDAD (mismo patrón que `equipos_medicion.equipo_id`, DA-13):
lo que se muestra, se calcula y se imprime es siempre `val_teo_*`. Ningún
lector decide un valor con esta columna; el tripwire de abajo lo afirma por
AST y por comportamiento.

Rojo-antes-que-verde real: `git stash push` sobre `seiscientos_mensual.py` /
`ix_mensual.py` deja la columna en NULL en todos los casos.
"""
import ast
import os
import pathlib
import sqlite3
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.referencias_qc import fijar_referencia
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    DatabaseManager, PruebaMensual600)

RAIZ = pathlib.Path(__file__).resolve().parent.parent


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
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES ('lamaya', 'x', 'Luz Adriana Maya', 1, '1', 'Físico Médico', 'jefe')")
    con.commit()
    con.close()
    for nombre in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, nombre, staticmethod(lambda *a, **k: None))
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _fijar(equipo, energia, valor):
    ok, motivo = fijar_referencia(
        equipo, "calidad", energia, valor, "puesta en servicio",
        "valor medido en la puesta en servicio", "lamaya")
    assert ok, motivo


def _crear_control(ruta, control_id, equipo, mes):
    """idx_controles_unico_mes: un mes distinto por control del mismo equipo."""
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, ?, 'Mensual', ?, 'Físico de Prueba')", (control_id, equipo, mes))
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(control_id)))
    con.commit()
    con.close()


def _filas(ruta, ref, energia="6mv"):
    """Todas las generaciones: [(activo, origen, val_teo_calidad)], la más
    vieja primero."""
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT activo, origen_referencia, val_teo_calidad FROM dosimetriaMen "
        "WHERE ref=? AND energia=? ORDER BY rowid", (ref, energia)).fetchall()
    con.close()
    return filas


def _vigente(ruta, ref, energia="6mv"):
    vigentes = [f for f in _filas(ruta, ref, energia) if f[0] in (None, 1)]
    assert len(vigentes) == 1, f"debe haber UNA fila vigente, hay {len(vigentes)}"
    return vigentes[0]


def _calidad_attr(energia):
    return (f"ln_calidad_pdd20_10_{energia}" if energia.endswith("mv")
            else f"ln_calidad_j2_j1_{energia}")


def _pelado(clase, equipo_f, energias):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj._debounce_timers = {}
    obj.equipo_f = equipo_f
    obj.ENERGIAS = list(energias)
    for e in energias:
        setattr(obj, f"val_teo_{e}", QLineEdit(""))
        setattr(obj, _calidad_attr(e), QLineEdit("0.66"))
    obj.ln_observaciones_dosi = QLineEdit("")
    return obj


def _df_lines(energias):
    lineas = []
    for e in energias:
        lineas += [f"val_teo_{e}", _calidad_attr(e)]
    return lineas + ["ln_observaciones_dosi"]


def _abrir_600(equipo, ref):
    """Camino real de apertura del 600/Halcyon: BD primero, precarga después."""
    obj = _pelado(PruebaMensual600, equipo, ["6mv"])
    df = _df_lines(["6mv"])
    obj._cargar_de_bd(df, "dosimetriaMen", ref)
    obj._precargar_referencia_calidad(df, "dosimetriaMen", ref)
    return obj, df


def _guardar_600(obj, df, ref):
    obj._subir_optimizado(df, "dosimetriaMen", 0, ref=ref, usarid=False)


def _abrir_ix(ref, energias=("6mv",)):
    obj = _pelado(PruebaMensualIX, "Clinac ix", energias)
    df = _df_lines(energias)
    obj._cargar_dosimetria_bd_ix(df, "dosimetriaMen", ref)
    obj._precargar_referencia_calidad(df, "dosimetriaMen", ref)
    return obj, df


def _guardar_ix(obj, df, ref):
    """La misma secuencia que `subir()` de addsomething_ix (ver el test de
    AST del final, que la ata al código real)."""
    obj._persistir_referencia_calidad_si_vacia(df)
    obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=ref, usarid=False, df_lines=df)
    obj._persistir_val_teo_dosis(ref)
    obj._persistir_origen_referencia(ref)


class TestLosTresOrigenesSeGuardanYSeReleen:
    def test_precargado_sin_tocar_es_tabla(self, app, bd_temporal):
        _crear_control(bd_temporal, 301, "Halcyon", "01/2026")
        _fijar("Halcyon", "6mv", 0.627)
        obj, df = _abrir_600("Halcyon", 301)
        assert obj.val_teo_6mv.text() == "0.627"
        _guardar_600(obj, df, 301)
        activo, origen, valor = _vigente(bd_temporal, 301)
        assert origen == "tabla"
        assert valor == pytest.approx(0.627)

    def test_tecleado_distinto_es_manual(self, app, bd_temporal):
        _crear_control(bd_temporal, 302, "Halcyon", "02/2026")
        _fijar("Halcyon", "6mv", 0.627)
        obj, df = _abrir_600("Halcyon", 302)
        obj.val_teo_6mv.setText("0.640")
        _guardar_600(obj, df, 302)
        _, origen, valor = _vigente(bd_temporal, 302)
        assert origen == "manual"
        assert valor == pytest.approx(0.640)

    def test_vacio_sin_referencia_es_respaldo(self, app, bd_temporal):
        _crear_control(bd_temporal, 303, "Clinac 600", "03/2026")
        obj, df = _abrir_600("Clinac 600", 303)
        assert obj.val_teo_6mv.text() == ""
        _guardar_600(obj, df, 303)
        _, origen, valor = _vigente(bd_temporal, 303)
        assert origen == "respaldo"
        assert valor == pytest.approx(0.665)

    def test_tecleado_sin_referencia_en_la_tabla_es_manual(self, app, bd_temporal):
        _crear_control(bd_temporal, 304, "Clinac 600", "04/2026")
        obj, df = _abrir_600("Clinac 600", 304)
        obj.val_teo_6mv.setText("0.6667")
        _guardar_600(obj, df, 304)
        _, origen, _ = _vigente(bd_temporal, 304)
        assert origen == "manual"

    def test_el_mismo_numero_de_la_tabla_tecleado_a_mano_sigue_siendo_tabla(
            self, app, bd_temporal):
        """Se compara el NÚMERO, no el texto: '0.6270' es la referencia."""
        _crear_control(bd_temporal, 305, "Halcyon", "05/2026")
        _fijar("Halcyon", "6mv", 0.627)
        obj, df = _abrir_600("Halcyon", 305)
        obj.val_teo_6mv.setText("0.6270")
        _guardar_600(obj, df, 305)
        assert _vigente(bd_temporal, 305)[1] == "tabla"

    def test_ix_cada_energia_su_propio_origen_en_el_mismo_guardado(
            self, app, bd_temporal):
        _crear_control(bd_temporal, 306, "Clinac ix", "06/2026")
        _fijar("Clinac ix", "6mv", 0.665)
        _fijar("Clinac ix", "15mv", 0.761)
        obj, df = _abrir_ix(306, ("6mv", "15mv", "6mev"))
        obj.val_teo_15mv.setText("0.700")  # el físico la cambia ese día
        # 6mev: sin referencia y vacío -> respaldo
        _guardar_ix(obj, df, 306)
        assert _vigente(bd_temporal, 306, "6mv")[1] == "tabla"
        assert _vigente(bd_temporal, 306, "15mv")[1] == "manual"
        assert _vigente(bd_temporal, 306, "6mev")[1] == "respaldo"
        assert _vigente(bd_temporal, 306, "6mev")[2] == pytest.approx(0.483)


class TestReguardarConservaElOrigen:
    """Reguardar reemplaza la fila (anula e inserta): la nueva no puede
    perder el origen de la anterior si el número no cambió."""

    @pytest.mark.parametrize("origen_inicial,preparar", [
        ("tabla", lambda o: None),
        ("manual", lambda o: o.val_teo_6mv.setText("0.640")),
        ("respaldo", lambda o: None),
    ])
    def test_sin_cambios_el_origen_se_conserva(
            self, app, bd_temporal, origen_inicial, preparar):
        ref = {"tabla": 311, "manual": 312, "respaldo": 313}[origen_inicial]
        equipo = "Clinac 600" if origen_inicial == "respaldo" else "Halcyon"
        _crear_control(bd_temporal, ref, equipo, f"0{ref - 310}/2026")
        if origen_inicial != "respaldo":
            _fijar("Halcyon", "6mv", 0.627)
        obj, df = _abrir_600(equipo, ref)
        preparar(obj)
        _guardar_600(obj, df, ref)
        assert _vigente(bd_temporal, ref)[1] == origen_inicial

        # Se cambia la referencia de la tabla DESPUÉS de firmar: no debe
        # arrastrar el origen ni el valor del control ya guardado.
        if origen_inicial != "respaldo":
            _fijar("Halcyon", "6mv", 0.700)

        obj2, df2 = _abrir_600(equipo, ref)
        _guardar_600(obj2, df2, ref)

        filas = _filas(bd_temporal, ref)
        assert len(filas) == 2, "el reguardado anula e inserta"
        assert [f[0] for f in filas] == [0, 1]
        assert filas[1][1] == origen_inicial
        assert filas[1][2] == filas[0][2]  # el valor tampoco cambió

    def test_historico_sin_origen_sigue_sin_origen(self, app, bd_temporal):
        """Una fila de antes de B.4 (origen NULL) reguardada sin cambios no
        se etiqueta: no se sabe de dónde salió y no se inventa."""
        _crear_control(bd_temporal, 314, "Halcyon", "07/2026")
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO dosimetriaMen (ref, energia, val_teo_calidad, val_teo_dosis) "
            "VALUES (314, '6mv', 0.627, 1.0009)")
        con.commit()
        con.close()
        _fijar("Halcyon", "6mv", 0.700)
        obj, df = _abrir_600("Halcyon", 314)
        assert obj.val_teo_6mv.text() == "0.627"
        _guardar_600(obj, df, 314)
        _, origen, valor = _vigente(bd_temporal, 314)
        assert origen is None
        assert valor == pytest.approx(0.627)

    def test_cambiar_el_valor_de_un_control_con_origen_tabla_lo_vuelve_manual(
            self, app, bd_temporal):
        _crear_control(bd_temporal, 315, "Halcyon", "08/2026")
        _fijar("Halcyon", "6mv", 0.627)
        obj, df = _abrir_600("Halcyon", 315)
        _guardar_600(obj, df, 315)
        assert _vigente(bd_temporal, 315)[1] == "tabla"

        obj2, df2 = _abrir_600("Halcyon", 315)
        obj2.val_teo_6mv.setText("0.631")
        _guardar_600(obj2, df2, 315)
        assert _vigente(bd_temporal, 315)[1:] == ("manual", pytest.approx(0.631))

    def test_guardar_dos_veces_seguidas_en_la_misma_pantalla_no_cambia_el_origen(
            self, app, bd_temporal):
        """Tras el primer guardado el widget YA contiene el respaldo: el
        segundo no puede creer que ese número lo tecleó alguien."""
        _crear_control(bd_temporal, 316, "Clinac 600", "09/2026")
        obj, df = _abrir_600("Clinac 600", 316)
        _guardar_600(obj, df, 316)
        _guardar_600(obj, df, 316)
        assert _vigente(bd_temporal, 316)[1] == "respaldo"

    def test_ix_reguardar_conserva_el_origen_de_cada_energia(self, app, bd_temporal):
        _crear_control(bd_temporal, 317, "Clinac ix", "10/2026")
        _fijar("Clinac ix", "6mv", 0.665)
        obj, df = _abrir_ix(317, ("6mv", "15mv"))
        obj.val_teo_15mv.setText("0.700")
        _guardar_ix(obj, df, 317)

        obj2, df2 = _abrir_ix(317, ("6mv", "15mv"))
        _guardar_ix(obj2, df2, 317)
        assert _vigente(bd_temporal, 317, "6mv")[1] == "tabla"
        assert _vigente(bd_temporal, 317, "15mv")[1] == "manual"


class TestLaColumnaSoloTrazaNoCambiaNadaMas:
    def test_el_resto_de_la_fila_es_identico_con_y_sin_el_origen(
            self, app, bd_temporal, monkeypatch):
        """El UPDATE es dirigido: además del origen, la fila guardada es la
        misma que daba A.2. (Se compara contra el guardado con el método
        anulado.)"""
        _crear_control(bd_temporal, 321, "Halcyon", "01/2027")
        _crear_control(bd_temporal, 322, "Halcyon", "02/2027")
        _fijar("Halcyon", "6mv", 0.627)

        obj, df = _abrir_600("Halcyon", 321)
        _guardar_600(obj, df, 321)
        monkeypatch.setattr(PruebaMensual600, "_persistir_origen_referencia",
                            lambda self, ref: None)
        obj2, df2 = _abrir_600("Halcyon", 322)
        _guardar_600(obj2, df2, 322)

        con = sqlite3.connect(bd_temporal)
        con.row_factory = sqlite3.Row
        a = dict(con.execute("SELECT * FROM dosimetriaMen WHERE ref=321").fetchone())
        b = dict(con.execute("SELECT * FROM dosimetriaMen WHERE ref=322").fetchone())
        con.close()
        for fila in (a, b):
            fila.pop("ref")
        assert a.pop("origen_referencia") == "tabla"
        assert b.pop("origen_referencia") is None
        assert a == b

    def test_solo_toca_la_fila_vigente(self, app, bd_temporal):
        """La generación superada conserva el origen que tenía."""
        _crear_control(bd_temporal, 323, "Halcyon", "03/2027")
        _fijar("Halcyon", "6mv", 0.627)
        obj, df = _abrir_600("Halcyon", 323)
        _guardar_600(obj, df, 323)
        obj2, df2 = _abrir_600("Halcyon", 323)
        obj2.val_teo_6mv.setText("0.650")
        _guardar_600(obj2, df2, 323)
        filas = _filas(bd_temporal, 323)
        assert [(f[0], f[1]) for f in filas] == [(0, "tabla"), (1, "manual")]


class TestNingunLectorDecideConElOrigen:
    """El origen es rastro, no criterio (DA-13): lo que se muestra y se
    calcula sale siempre de val_teo_*."""

    # (archivo, función) donde el nombre de la columna puede aparecer:
    # la migración que la crea, el lector que la LEE solo para conservarla
    # al reguardar, y el escritor. Nada más.
    PERMITIDOS = {
        ("data/ManejoDatos/conection.py", "_asegurar_origen_referencia_dosimetria"),
        ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py",
         "_energias_con_fila_vigente"),
        ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py",
         "_persistir_origen_referencia"),
    }

    def _menciones_en_produccion(self):
        halladas = set()
        for ruta in RAIZ.rglob("*.py"):
            rel = ruta.relative_to(RAIZ).as_posix()
            if rel.startswith(("tests/", ".venv/", "build/", "dist/")):
                continue
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for func in ast.walk(arbol):
                if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for nodo in ast.walk(func):
                    if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                            and "origen_referencia" in nodo.value):
                        halladas.add((rel, func.name))
        return halladas

    def test_el_censo_de_produccion_es_exactamente_el_autorizado(self):
        assert self._menciones_en_produccion() == self.PERMITIDOS

    def test_el_censo_discrimina(self, tmp_path, monkeypatch):
        """Un lector nuevo que mencione la columna DEBE aparecer en el censo:
        se simula añadiéndolo a un archivo temporal dentro de la raíz."""
        intruso = RAIZ / "services" / "_intruso_b4_tmp.py"
        intruso.write_text(
            "def decide(cur):\n"
            "    return cur.execute('SELECT origen_referencia FROM dosimetriaMen')\n")
        try:
            extra = self._menciones_en_produccion() - self.PERMITIDOS
        finally:
            intruso.unlink()
        assert extra == {("services/_intruso_b4_tmp.py", "decide")}

    @pytest.mark.parametrize("origen", [None, "tabla", "manual", "respaldo"])
    def test_lo_mostrado_y_lo_calculado_no_dependen_del_origen(
            self, app, bd_temporal, origen):
        ref = 330 + [None, "tabla", "manual", "respaldo"].index(origen)
        _crear_control(bd_temporal, ref, "Halcyon", f"0{ref - 329}/2028")
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO dosimetriaMen (ref, energia, val_teo_calidad, origen_referencia) "
            "VALUES (?, '6mv', 0.627, ?)", (ref, origen))
        con.commit()
        con.close()
        _fijar("Halcyon", "6mv", 0.700)

        obj, _ = _abrir_600("Halcyon", ref)
        obj.ln_dosis_ref_cgy_um_6mv = QLineEdit("")
        obj.ln_discrepancia_dosis_6mv = QLineEdit("")
        obj.ln_discrepancia_calidad_6mv = QLineEdit("")
        obj.ln_calidad_pdd20_10_6mv.setText("0.62")
        obj.discrepancias()

        assert obj.val_teo_6mv.text() == "0.627"
        assert float(obj.ln_discrepancia_calidad_6mv.text()) == pytest.approx(1.12, abs=0.01)


class TestLaSecuenciaRealDelIxLlamaAlEscritor:
    """`subir()` es un closure dentro de addsomething_ix, así que los tests
    de arriba replican su secuencia; este ata la réplica al código real."""

    def test_subir_del_ix_persiste_el_origen_despues_del_guardado(self):
        fuente = (RAIZ / "ui/paginasControles/PruebasMensuales/ix_mensual.py").read_text()
        orden = ["self._persistir_referencia_calidad_si_vacia(",
                 "self.subirlineasmensuales_ix(",
                 "self._persistir_val_teo_dosis(",
                 "self._persistir_origen_referencia("]
        posiciones = [fuente.index(t) for t in orden]
        assert posiciones == sorted(posiciones)

    def test_subir_del_600_persiste_el_origen_despues_del_guardado(self):
        fuente = (RAIZ / "ui/paginasControles/PruebasMensuales/seiscientos_mensual.py"
                  ).read_text()
        inicio = fuente.index("def _subir_optimizado(")
        cuerpo = fuente[inicio:inicio + 2500]
        orden = ["self._persistir_referencia_calidad_si_vacia(",
                 "subirlineasmensuales(self,",
                 "self._persistir_val_teo_dosis(",
                 "self._persistir_origen_referencia("]
        posiciones = [cuerpo.index(t) for t in orden]
        assert posiciones == sorted(posiciones)
