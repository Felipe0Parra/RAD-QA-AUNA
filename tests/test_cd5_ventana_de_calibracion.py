"""CD.5 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-90, DA-92): la ventana de calibración de las películas (`ui/paginasControles/PruebasMensuales/curva_dosis.py`) y sus dibujos
(`analisisImagenes/dibujo_curva_dosis.py`).

El camino de una persona: abrir la ventana (arranca con la plantilla de P12), cargar las 11 piezas sintéticas con «Cargar imagen...» (la pieza se mide con el cursor de espera), escribir las dosis
medidas en la tabla, ver el gráfico ÚNICO de las cuatro capas con los residuos debajo y la tabla de la curva, guardar, abrir (se ve y no se edita) y anular (con el permiso). Además: la curva de la
pantalla es la que se guarda (CD5-D1), lo guardado lleva la dosis MEDIDA, la tabla de la curva y los residuos son los del motor, la curva no se extrapola y su tramo fuera del rango útil va punteado, una
pieza dañada dice por qué, el cursor se restaura aunque la medición falle, lo que rechaza el servicio se dice tal cual, «Nueva» deja la ventana como recién creada, y la ventana no tiene SQL (AST).

Todo lo de producción se importa POR PRUEBA: contra HEAD (sin CD.5) cada prueba cae con su `ModuleNotFoundError`, no con un error de colección. Trampa 2: todo cuadro se parcha (`dialogos`); Trampa 9:
cada ventana se cierra con `cerrar` de las pruebas de E.1. El catálogo de equipos se sustituye por uno fijo (`catalogo`): la ventana lo lee por `EquiposService`, que no se prueba aquí.

AMPLIADA POR EL IMPLEMENTADOR (31-10-2026, sección (8) al final; los 41 casos de la referencia del pre-vuelo no se tocaron): la cobertura de líneas de la prueba de referencia (`scripts/cd5_cobertura_lineas.py` del anexo:
90.5 % de la ventana y 95.9 % del dibujo) dejó SIN prueba conductas que el bloque de CD.5 y las decisiones del pre-vuelo nombran: quitar y agregar filas (con réplicas), editar la dosis nominal (también por el editor
REAL de Qt), una dosis que no es un número, la hora de irradiación (CD5-D2) y todo el encabezado de ida y vuelta (CD5-D3), el catálogo que no se puede leer o el equipo que ya no está, lo que el servicio rechaza al abrir,
recalcular y anular dicho tal cual, la pregunta de anular ANTES del permiso (CD5-D7), «Nueva» que se responde que no (CD5-D11), la película virgen que hace de cero o no se puede leer (DC3), el aviso de 20 MB (DC14) y
el indicador de espera. Cada una tiene su mutación en `cd5_mutaciones.py` (las X01 en adelante).

CORREGIDA POR EL CORRECTOR (31-10-2026, ronda 1 de la revisión escéptica; sección (9) al final y dos pruebas reforzadas en su sitio): los 16 hallazgos reproducidos (CD5-PROD-R1-01 a 09 y CD5-PR-1 a 7; 14 defectos distintos: R1-03 = PR-5 y R1-04 = PR-1). Cinco
mutaciones plausibles que ninguna prueba atrapaba (una virgen montada no válida, el orden guardado al abrir, la de 0 cGy sin dosis medida, volver a cargar una fila, las coordenadas del gráfico) y dos pruebas
más débiles que su nombre (`test_abrir_se_ve_y_no_se_edita`, `test_abrir_por_la_lista`) quedaron cubiertas, y los defectos de producción que la revisión midió (el aviso de «sin cero», la celda «no medible» de una
pieza bien medida, el reemplazo en silencio de la vigente, la hora con un superíndice, un error inesperado al medir, «Nueva» que deja lo escrito en un menú editable y el factor del catálogo redondeado) tienen su
prueba, escrita ANTES de tocar la producción. Cada una tiene su mutación en `cd5_mutaciones.py` (las Y01 en adelante)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import ast
import copy
import importlib
import io
import json
import re
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QComboBox, QDateEdit, QDialog, QFileDialog, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget

import _piezas_de_calibracion_sinteticas as gen
import data.ManejoDatos.conection as conection_mod
from _e1_ayudas import _virgen_sintetica, cerrar, recorrer, sin_simbolos
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import crear_indices

RAIZ = Path(__file__).resolve().parent.parent
VENTANA_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "curva_dosis.py"
DIBUJO_PY = RAIZ / "analisisImagenes" / "dibujo_curva_dosis.py"
BUILD_PY = RAIZ / "build_exe.py"
USUARIO = "Fisico de prueba"
CAPAS = ("R", "G", "B", "gris")
PLANTILLA = (0, 50, 100, 150, 200, 300, 400, 500, 600, 800, 1000)
DEVIC = (gen.RespuestaDevic(700.0, 3300.0, 2.06), gen.RespuestaDevic(1100.0, 4600.0, 2.19), gen.RespuestaDevic(1750.0, 8200.0, 1.58))
GRANDE = 50.0                                     # piezas de 5 x 5 cm: con el ruido de EPSON179 las cuatro capas salen «válidas» (como en CD.4)
VALIDA = "válida"
CARPETA = "calibraciones_pelicula_escaneos"
CATALOGO = {"Cámara de ionización": {"FC65-G": [(19, "1234", "2026-03-17", 4.85e-2)]}, "Electrómetro": {"Dose 1": [(31, "5678", "2026-03-17", None)]}}
UNIDAD_ENTRE_PARENTESIS = re.compile(r"\((?:cGy|Gy|cm|mm|%|MB|ppp|h)\)")


def ventana_mod():
    return importlib.import_module("ui.paginasControles.PruebasMensuales.curva_dosis")


def dibujo_mod():
    return importlib.import_module("analisisImagenes.dibujo_curva_dosis")


def svc():
    return importlib.import_module("services.curva_dosis")


def motor():
    return importlib.import_module("analisisImagenes.curva_dosis")


def pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _P():
    return copy.deepcopy(importlib.import_module("analisisImagenes.placa_mensual").VALORES_DE_LA_GEOMETRIA)


def _sql(ruta, consulta, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(consulta, parametros).fetchall()
    finally:
        con.close()


def _json(valor):
    return json.loads(json.dumps(valor))


# ===================================================================================================== las piezas, la base y los cuadros

def _juego(respuestas=DEVIC, **opciones):
    salida = {}
    for k, d in enumerate(PLANTILLA):
        salida[k + 1] = (d, f"{d}.tif", gen.pieza_de_dosis(d, respuestas, lado_mm=GRANDE, semilla=k + 1, **opciones).datos)
    return salida


@pytest.fixture(scope="module")
def escaneos():
    """Los bytes de una calibración sintética (la plantilla de P12 en piezas de 5 x 5 cm): {orden: (dosis, nombre, bytes)}; la de 0 cGy es la 1."""
    return _juego()


@pytest.fixture(scope="module")
def escaneos_con_el_rojo_recortado():
    return _juego(negro_desde_cgy={"R": 300})


@pytest.fixture(scope="module")
def escaneos_saturantes():
    """Una película que se satura (CD.3): las dosis altas no se distinguen y quedan FUERA del rango útil con su netOD (el tramo punteado y las piezas huecas)."""
    return _juego(gen.RespuestaSaturante(0.30, 120.0))          # medido en el pre-vuelo: la roja deja la de 1000 cGy fuera (no se distingue de la de 800)


@pytest.fixture(scope="module")
def escaneos_a_600_ppp():
    """(ampliación del implementador) Las diez piezas irradiadas de la plantilla (sin la de 0 cGy) de 2 x 2 cm a 600 ppp: la cadena de captura de la película virgen sintética de `_virgen_a_600` (CD.3: la virgen
    solo hace de cero si es de la misma cadena que las piezas, como en las pruebas de CD.4). {orden: (dosis, nombre, bytes)} con el orden de su fila (2 a 11)."""
    return {k + 1: (d, f"{d}.tif", gen.pieza_de_dosis(d, DEVIC, lado_mm=20.0, dpi=600.0, semilla=k + 1).datos) for k, d in enumerate(PLANTILLA) if d > 0}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _cursor_limpio(app):
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()
    yield
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    ruta = str(tmp_path_factory.mktemp("cd5") / "plantilla.db")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
            Conexion._instance = None
            crear_indices(ruta)
        finally:
            Conexion._instance = previo
    return ruta


@pytest.fixture
def bd(plantilla, monkeypatch, tmp_path):
    """Una copia de la plantilla en su propia carpeta (los escaneos y la película virgen van junto a ella) y un `Conexion` sin arranque: `conectar()` es el real."""
    carpeta = tmp_path / "base"
    carpeta.mkdir()
    ruta = str(carpeta / "cd5.db")
    shutil.copy(plantilla, ruta)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    previo = Conexion._instance
    Conexion._instance = object.__new__(Conexion)
    yield ruta
    Conexion._instance = previo


@pytest.fixture(autouse=True)
def catalogo(monkeypatch):
    """El catálogo de equipos, fijo y mutable por la prueba (la ventana lo lee por `EquiposService`)."""
    from services.equipos_service import EquiposService
    datos = copy.deepcopy(CATALOGO)
    monkeypatch.setattr(EquiposService, "modelos_actuales", staticmethod(lambda tipo: sorted(datos.get(tipo, {}))))
    monkeypatch.setattr(EquiposService, "calibraciones_activas", staticmethod(lambda tipo, modelo: [(i, s, f, tipo) for i, s, f, _x in datos.get(tipo, {}).get(modelo, [])]))

    def por_id(equipo_id):
        for tipo, modelos in datos.items():
            for modelo, filas in modelos.items():
                for i, s, f, factor in filas:
                    if i == equipo_id:
                        return {"id": i, "equip_type": tipo, "model": modelo, "serie": s, "calibr_fact": factor}
        return None
    monkeypatch.setattr(EquiposService, "obtener_por_id", staticmethod(por_id))
    return datos


class Dialogos:
    def __init__(self):
        self.llamadas = []
        self.respuesta = QMessageBox.Yes
        self.ruta = ""
        self.elegido = None
        self.permiso = QDialog.DialogCode.Accepted
        self.permisos_pedidos = []

    def anotar(self, tipo, args):
        cursor = QApplication.overrideCursor()
        self.llamadas.append({"tipo": tipo, "titulo": args[1] if len(args) > 1 else None, "texto": args[2] if len(args) > 2 else None, "cursor": None if cursor is None else cursor.shape()})

    def de(self, tipo):
        return [c for c in self.llamadas if c["tipo"] == tipo]


@pytest.fixture
def dialogos(monkeypatch):
    d = Dialogos()

    def sustituto(tipo, devuelve):
        def f(*args, **kwargs):
            d.anotar(tipo, args)
            return devuelve() if callable(devuelve) else devuelve
        return staticmethod(f)
    monkeypatch.setattr(QMessageBox, "warning", sustituto("warning", QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "information", sustituto("information", QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "critical", sustituto("critical", QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", sustituto("question", lambda: d.respuesta))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (d.ruta, "")))

    def elegir(*args, **kwargs):
        d.anotar("elegir", args)
        textos = args[3]
        return (textos[0] if d.elegido is None else d.elegido), True
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(elegir))

    class PermisoFalso:
        def __init__(self, usuario, *a, **k):
            d.permisos_pedidos.append(usuario)

        def exec(self):
            d.anotar("permiso", ())
            return d.permiso
        exec_ = exec
    try:
        monkeypatch.setattr(ventana_mod(), "DialogAdminPermisoEliminar", PermisoFalso)
    except ImportError:                                  # en HEAD la ventana no existe: cada prueba cae por su cuenta
        pass
    yield d
    assert not d.de("critical"), f"un cuadro de error inesperado: {[c['texto'] for c in d.de('critical')]}"
    assert all(c["cursor"] is None for c in d.llamadas), "un cuadro se abrió con el cursor de espera puesto"
    con_simbolos = [c for c in d.llamadas if not all(sin_simbolos(t) for t in (c["titulo"], c["texto"]) if isinstance(t, str))]
    assert not con_simbolos, f"un cuadro con símbolos de correcto o incorrecto (DA-18): {con_simbolos}"


@pytest.fixture
def fabrica(app, bd, dialogos):
    creadas = []

    def crear(usuario=USUARIO):
        v = ventana_mod().VentanaCurvaDosis(usuario)
        v.resize(1380, 880)
        creadas.append(v)
        return v
    yield crear
    for v in creadas:
        cerrar(v)


@pytest.fixture
def ventana(fabrica):
    return fabrica()


# ===================================================================================================== el camino del usuario

def _boton(v, fila, columna):
    return v.tabla_piezas.cellWidget(fila, columna)


def cargar(v, dialogos, tmp_path, fila, nombre, datos):
    """El físico pulsa «Cargar imagen...» de esa fila y elige el archivo."""
    ruta = tmp_path / "escaneos" / nombre
    ruta.parent.mkdir(exist_ok=True)
    ruta.write_bytes(datos)
    dialogos.ruta = str(ruta)
    _boton(v, fila, dibujo_mod().COLUMNA_CARGAR).click()


def escribir(v, fila, columna, texto):
    """El físico escribe en una celda de la tabla de piezas (la señal `itemChanged` de Qt, la de la edición real)."""
    v.tabla_piezas.item(fila, columna).setText(texto)


def cargar_todas(v, dialogos, tmp_path, escaneos, medidas=None, cuales=None):
    """Carga las piezas de la plantilla en su fila y escribe su dosis medida (la nominal, o la de `medidas`)."""
    for orden, (d, nombre, datos) in sorted(escaneos.items()):
        if cuales is not None and orden not in cuales:
            continue
        cargar(v, dialogos, tmp_path, orden - 1, nombre, datos)
        escribir(v, orden - 1, dibujo_mod().COLUMNA_MEDIDA, f"{(medidas or {}).get(orden, d):g}")


def llenar_el_encabezado(v, lote="L-01"):
    v.lote.setText(lote)
    v.energia.setEditText("6 MV")
    v.profundidad.setText("3")
    v.dfs.setText("100")
    v.campo.setText("10 × 10")
    v.u_dosis.setText("1,5")
    v.camara.setCurrentIndex(1)
    v.electrometro.setCurrentIndex(1)


def celdas(tabla):
    return [[tabla.item(r, c).text() if tabla.item(r, c) else None for c in range(tabla.columnCount())] for r in range(tabla.rowCount())]


def guardada(v, dialogos, tmp_path, escaneos, **k):
    cargar_todas(v, dialogos, tmp_path, escaneos, **k)
    llenar_el_encabezado(v)
    v.boton_guardar.click()
    assert v.estado == "registro", [c["texto"] for c in dialogos.llamadas]
    return v._registro["id"]


def la_curva_del_motor(escaneos, medidas=None, virgen=None, u=1.5):
    """La verdad: CD.2 y CD.3 llamados AQUÍ sobre los mismos bytes, con los mismos nombres de archivo."""
    piezas = [motor().pieza_de_calibracion(o, float(d), float((medidas or {}).get(o, d)), pel().medir_pieza_uniforme(datos, _P(), nombre, "2026-10-30", escala="declarada"))
              for o, (d, nombre, datos) in sorted(escaneos.items())]
    return motor().ajustar(piezas, virgen=virgen, u_dosis_medida_pct=u)


def huella(v):
    """Lo observable de la ventana, del árbol de widgets (no de una lista de lo que «Nueva» limpia), de los ejes de la figura y de los atributos simples."""
    widgets = []
    for w in recorrer(v):
        e = [type(w).__name__, w.isEnabled(), w.isVisibleTo(v)]
        if isinstance(w, QLineEdit):
            e += [w.text(), w.isReadOnly()]
        elif isinstance(w, QLabel):
            e += [w.text()]
        elif isinstance(w, QComboBox):
            e += [w.count(), w.currentIndex(), w.currentText(), tuple(w.itemData(i) for i in range(w.count())), tuple(w.itemText(i) for i in range(w.count()))]
        elif isinstance(w, QPushButton):
            e += [w.text(), w.isChecked()]
        elif isinstance(w, QDateEdit):
            e += [w.date().toString("yyyy-MM-dd")]
        elif isinstance(w, QTableWidget):
            e += [w.rowCount(), tuple(map(tuple, celdas(w))),
                  tuple(tuple(bool(w.item(r, c).flags() & Qt.ItemIsEditable) if w.item(r, c) else None for c in range(w.columnCount())) for r in range(w.rowCount())),
                  tuple(tuple((type(w.cellWidget(r, c)).__name__, w.cellWidget(r, c).isEnabled()) if w.cellWidget(r, c) else None for c in range(w.columnCount())) for r in range(w.rowCount()))]
        widgets.append(tuple(e))
    ejes = tuple((eje.get_title(), eje.get_xlabel(), eje.get_ylabel(), tuple(t.get_text() for t in eje.texts), len(eje.lines), len(eje.collections)) for eje in v.figura.axes)
    simples = {k: val for k, val in vars(v).items() if isinstance(val, (str, int, float, bool, type(None)))}
    filas = [{k: val for k, val in f.items() if k != "medida"} | {"medida": f["medida"] is not None} for f in v._filas]
    return widgets, ejes, simples, filas, v._curva is None, v._registro is None, v._recalculo is None


def _virgen_a_600():
    """(ampliación del implementador) (bytes, referencia) de una película virgen sintética de 6 x 6 cm a 600 ppp con el I0 de EPSON179, como la de las pruebas de CD.4: válida y de la cadena de captura de las piezas
    de `escaneos_a_600_ppp`."""
    lienzo = gen.Lienzo(66.0, 66.0, 600.0, semilla=9)
    lienzo.pegar_pelicula(3.0, 3.0, 60.0, 60.0, gen.I0_EPSON179, gen.RUIDO_EPSON179)
    datos = lienzo.codificar()
    return datos, pel().piso_de_pelicula_virgen(datos, _P(), "virgen.tif", "2026-10-30")


def editar_con_el_editor(v, fila, columna, texto):
    """(ampliación del implementador) El físico hace doble clic en la celda, escribe en el editor que Qt abre y pulsa Enter: la edición REAL, no `item.setText`. La ventana reemplaza los items de la tabla dentro de
    `itemChanged` (`_actualizar`), y aquí se ve que Qt lo tolera cuando el cambio viene del editor. La ventana tiene que estar mostrada."""
    tabla = v.tabla_piezas
    item = tabla.item(fila, columna)
    tabla.setCurrentItem(item)
    tabla.editItem(item)
    QApplication.processEvents()
    editor = tabla.findChild(QLineEdit)
    assert editor is not None, "Qt no abrió el editor de la celda"
    editor.selectAll()
    QTest.keyClicks(editor, texto)
    QTest.keyClick(editor, Qt.Key_Return)
    QApplication.processEvents()


# ===================================================================================================== (1) el camino de una persona

class TestElCaminoDeUnaPersona:
    def test_arranca_con_la_plantilla_de_p12(self, ventana):
        d = dibujo_mod()
        assert [ventana.tabla_piezas.horizontalHeaderItem(c).text() for c in range(ventana.tabla_piezas.columnCount())] == list(d.COLUMNAS_DE_LAS_PIEZAS)
        tabla = celdas(ventana.tabla_piezas)
        assert [f[d.COLUMNA_NOMINAL] for f in tabla] == [f"{x:g}" for x in PLANTILLA]
        assert tabla[0][d.COLUMNA_ARCHIVO] == "sin imagen (película virgen)" and all(f[d.COLUMNA_ARCHIVO] == "sin imagen" for f in tabla[1:])
        assert not ventana.boton_guardar.isEnabled() and not ventana.boton_anular.isEnabled() and ventana.boton_abrir.isEnabled()
        assert ventana.estado == "nueva" and ventana._curva is None

    def test_cargar_once_piezas_escribir_las_dosis_ver_la_curva_guardar_abrir_y_anular(self, ventana, dialogos, tmp_path, escaneos, bd):
        d = dibujo_mod()
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        assert ventana._curva is not None and [ventana._curva.estado(c) for c in CAPAS] == [VALIDA] * 4
        tabla = celdas(ventana.tabla_piezas)
        assert all(tabla[i][d.COLUMNA_ARCHIVO] == escaneos[i + 1][1] for i in range(11))
        assert all(re.fullmatch(r"\d\.\d{4} ± \d\.\d{4}", tabla[i][d.COLUMNA_DE_LA_CAPA[c]]) for i in range(11) for c in CAPAS), tabla
        gids = {l.get_gid() for l in ventana.eje_curva.lines}
        assert {f"curva_{c}_dentro" for c in CAPAS} <= gids
        assert ventana.eje_curva.get_legend() is not None and any(l.get_visible() for l in ventana.eje_curva.get_xgridlines())
        assert [f[7] for f in celdas(ventana.tabla_curva)] == [VALIDA] * 4
        llenar_el_encabezado(ventana)
        ventana.boton_guardar.click()
        assert ventana.estado == "registro"
        assert [c["tipo"] for c in dialogos.llamadas] == ["information"], dialogos.llamadas
        assert _sql(bd, "SELECT COUNT(*), SUM(activo) FROM calibracion_pelicula") == [(1, 1)]
        assert _sql(bd, "SELECT COUNT(*) FROM calibracion_pelicula_pieza WHERE activo = 1") == [(11,)]
        assert not ventana.lote.isEnabled() and not ventana.boton_guardar.isEnabled() and ventana.boton_anular.isEnabled()
        dialogos.respuesta = QMessageBox.Yes
        ventana.boton_anular.click()
        assert _sql(bd, "SELECT activo FROM calibracion_pelicula") == [(0,)]
        assert [a for (a,) in _sql(bd, "SELECT accion FROM audit_log WHERE tabla = 'calibracion_pelicula' ORDER BY id")] == ["guardar", "anular"]
        assert "anulada" in ventana.etiqueta_registro.text() and not ventana.boton_anular.isEnabled()

    def test_la_curva_de_la_pantalla_es_la_que_se_guarda(self, ventana, dialogos, tmp_path, escaneos):
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        llenar_el_encabezado(ventana)
        en_pantalla = _json(ventana._curva.como_dict())
        ventana.boton_guardar.click()
        guardado = svc().leer(ventana._registro["id"])
        assert guardado["ajuste"] == en_pantalla

    def test_lo_guardado_lleva_la_dosis_medida_y_no_la_nominal(self, ventana, dialogos, tmp_path, escaneos):
        medidas = {o: d * 1.02 + 1.0 for o, (d, _n, _b) in escaneos.items() if d > 0}
        id_ = guardada(ventana, dialogos, tmp_path, escaneos, medidas=medidas)
        piezas = {p["orden"]: p for p in svc().leer(id_)["piezas"]}
        assert {o: p["dosis_medida_cgy"] for o, p in piezas.items() if o in medidas} == pytest.approx(medidas)
        assert {o: p["dosis_nominal_cgy"] for o, p in piezas.items()} == {o: float(d) for o, (d, _n, _b) in escaneos.items()}

    def test_el_usuario_que_llega_al_servicio_es_un_texto_y_el_permiso_recibe_el_de_la_sesion(self, fabrica, dialogos, tmp_path, escaneos, bd):
        sesion = SimpleNamespace(_nombre="Ana Física", _usuario="ana")
        v = fabrica(sesion)
        guardada(v, dialogos, tmp_path, escaneos)
        v.boton_anular.click()
        assert _sql(bd, "SELECT usuario, activo FROM calibracion_pelicula") == [("Ana Física", 0)]
        assert {u for (u,) in _sql(bd, "SELECT usuario FROM audit_log WHERE tabla = 'calibracion_pelicula'")} == {"Ana Física"}
        assert dialogos.permisos_pedidos == [sesion]


# ===================================================================================================== (2) la tabla y el gráfico son los del motor

class TestLoQueSeVeEsLoDelMotor:
    def test_la_tabla_de_la_curva_y_los_residuos_son_los_del_motor(self, ventana, dialogos, tmp_path, escaneos):
        medidas = {o: d * (1.0 + 0.01 * ((o % 3) - 1)) for o, (d, _n, _b) in escaneos.items()}
        cargar_todas(ventana, dialogos, tmp_path, escaneos, medidas=medidas)
        ventana.u_dosis.setText("1.5")
        verdad = la_curva_del_motor(escaneos, medidas=medidas)
        filas = celdas(ventana.tabla_curva)
        for fila, c in zip(filas, CAPAS):
            capa = verdad.capas[c]
            assert fila[7] == capa["estado"]
            assert fila[6] == f"{capa['rms_pct']:.2f}"
            assert fila[1:4] == [f"{capa['parametros']['a']:.4g}", f"{capa['parametros']['b']:.4g}", f"{capa['parametros']['n']:.4f}"]
            assert fila[4] == f"de 0 a {capa['rango_cgy']:g}"
            residuos = [p.capas[c]["residuo_pct"] for p in verdad.piezas if p.capas[c]["en_el_rango"] and p.capas[c]["residuo_pct"] is not None]
            assert fila[5] == f"{max(residuos, key=abs):.2f}"
            puntos = next(l for l in ventana.eje_residuos.lines if l.get_gid() == f"residuos_{c}_dentro")
            assert list(puntos.get_ydata()) == pytest.approx(residuos)

    def test_la_curva_no_se_extrapola_y_fuera_del_rango_va_punteada(self, ventana, dialogos, tmp_path, escaneos_saturantes):
        cargar_todas(ventana, dialogos, tmp_path, escaneos_saturantes)
        curva = ventana._curva
        fuera = 0
        for c in CAPAS:
            ultima = max((p.capas[c]["netod"] for p in curva.piezas if p.capas[c]["netod"] is not None), default=None)
            lineas = [l for l in ventana.eje_curva.lines if (l.get_gid() or "").startswith(f"curva_{c}_")]
            if curva.capas[c]["parametros"] is None:
                assert not lineas
                continue
            assert max(max(l.get_xdata()) for l in lineas) == pytest.approx(ultima, abs=1e-12)
            for l in lineas:
                if l.get_gid().endswith("_fuera"):
                    fuera += 1
                    assert l.get_linestyle() == ":" and min(l.get_xdata()) == pytest.approx(curva.capas[c]["netod_maxima"])
                else:
                    assert l.get_linestyle() == "-" and max(l.get_xdata()) <= curva.capas[c]["netod_maxima"] + 1e-12
            huecas = [l for l in ventana.eje_curva.lines if l.get_gid() == f"piezas_{c}_fuera" and l.get_marker() == "o"]          # la línea de los puntos (matplotlib 3.10 pone el gid también a los topes de las barras)
            rellenas = [l for l in ventana.eje_curva.lines if l.get_gid() == f"piezas_{c}_dentro" and l.get_marker() == "o"]
            assert all(l.get_markerfacecolor() == "none" for l in huecas) and all(l.get_markerfacecolor() != "none" for l in rellenas)
        assert fuera >= 1, "el juego saturante debe dejar piezas fuera del rango útil (no vacuidad)"
        rotulos = ventana.eje_curva.get_legend_handles_labels()[1]
        assert [r for r in rotulos if r in ("capa roja", "capa verde", "capa azul", "gris")] == ["capa roja", "capa verde", "capa azul", "gris"]          # cada capa una vez en la leyenda


# ===================================================================================================== (3) una pieza dañada dice por qué

class TestUnaPiezaDanadaDicePorQue:
    def test_una_pieza_sin_resolucion_dice_el_motivo_en_cada_capa(self, ventana, dialogos, tmp_path):
        datos = gen.pieza_uniforme(lado_mm=GRANDE, dpi_declarado=None).datos
        cargar(ventana, dialogos, tmp_path, 1, "sin_ppp.tif", datos)
        medida = pel().medir_pieza_uniforme(datos, _P(), "sin_ppp.tif", "2026-10-30", escala="declarada")
        assert medida.estado.startswith("no medible")
        fila = celdas(ventana.tabla_piezas)[1]
        assert [fila[dibujo_mod().COLUMNA_DE_LA_CAPA[c]] for c in CAPAS] == [medida.estado] * 4

    def test_la_capa_recortada_lo_dice(self, ventana, dialogos, tmp_path, escaneos_con_el_rojo_recortado):
        cargar_todas(ventana, dialogos, tmp_path, escaneos_con_el_rojo_recortado)
        tabla = celdas(ventana.tabla_piezas)
        assert tabla[6][dibujo_mod().COLUMNA_DE_LA_CAPA["R"]] == "recortada por el escáner"          # la de 400 cGy
        assert tabla[6][dibujo_mod().COLUMNA_DE_LA_CAPA["G"]] != "recortada por el escáner"

    def test_el_cursor_se_restaura_si_la_medicion_falla(self, ventana, dialogos, tmp_path, monkeypatch, escaneos):
        def falla(*a, **k):
            assert QApplication.overrideCursor() is not None and QApplication.overrideCursor().shape() == Qt.WaitCursor
            raise ValueError("la medición se rompió a propósito")
        monkeypatch.setattr(pel(), "medir_pieza_uniforme", falla)
        cargar(ventana, dialogos, tmp_path, 1, "50.tif", escaneos[2][2])
        assert QApplication.overrideCursor() is None
        assert [c["texto"] for c in dialogos.de("warning")] == ["No se pudo medir la pieza «50.tif»: la medición se rompió a propósito"]
        assert celdas(ventana.tabla_piezas)[1][dibujo_mod().COLUMNA_ARCHIVO] == "sin imagen" and ventana._filas[1]["medida"] is None


# ===================================================================================================== (4) guardar

class TestGuardar:
    def test_sin_ninguna_pieza_medible_no_guarda(self, ventana, dialogos, tmp_path, bd):
        cargar(ventana, dialogos, tmp_path, 0, "sin_ppp.tif", gen.pieza_uniforme(lado_mm=GRANDE, dpi_declarado=None).datos)
        llenar_el_encabezado(ventana)
        assert ventana.boton_guardar.isEnabled()
        ventana.boton_guardar.click()
        assert [c["texto"] for c in dialogos.de("warning")] == [ventana_mod().NO_GUARDA_SIN_CERO]
        assert _sql(bd, "SELECT COUNT(*) FROM calibracion_pelicula") == [(0,)]

    def test_sin_la_pieza_de_0_cgy_pregunta_y_dice_de_donde_sale_el_cero(self, ventana, dialogos, tmp_path, escaneos, bd):
        cargar_todas(ventana, dialogos, tmp_path, escaneos, cuales=set(range(2, 12)))
        llenar_el_encabezado(ventana)
        dialogos.respuesta = QMessageBox.No
        ventana.boton_guardar.click()
        preguntas = dialogos.de("question")
        assert len(preguntas) == 1 and f"La curva no tiene una pieza de 0 cGy: {ventana._curva.cero['detalle']}." in preguntas[0]["texto"]
        assert _sql(bd, "SELECT COUNT(*) FROM calibracion_pelicula") == [(0,)]
        dialogos.respuesta = QMessageBox.Yes
        ventana.boton_guardar.click()
        assert svc().leer(ventana._registro["id"])["cero"]["fuente"] == "pieza_de_menor_dosis"

    def test_una_dosis_medida_que_falta_se_confirma(self, ventana, dialogos, tmp_path, escaneos, bd):
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        escribir(ventana, 2, dibujo_mod().COLUMNA_MEDIDA, "")
        llenar_el_encabezado(ventana)
        dialogos.respuesta = QMessageBox.No
        ventana.boton_guardar.click()
        texto = dialogos.de("question")[0]["texto"]
        assert "Falta la dosis medida de: fila 3 (100 cGy)." in texto and "Estas capas no salen «válida»" in texto
        assert _sql(bd, "SELECT COUNT(*) FROM calibracion_pelicula") == [(0,)]

    @pytest.mark.parametrize("lote, u", [("   ", "1,5"), ("L-01", "-1")], ids=["lote_en_blanco", "incertidumbre_negativa"])
    def test_lo_que_rechaza_el_servicio_se_dice_tal_cual(self, ventana, dialogos, tmp_path, escaneos, bd, lote, u):
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        llenar_el_encabezado(ventana, lote=lote)
        ventana.u_dosis.setText(u)
        encabezado, _p = ventana.encabezado()
        piezas, _q = ventana.piezas()
        with pytest.raises(svc().CurvaDosisError) as rechazo:
            svc().guardar(USUARIO, encabezado, piezas)
        assert len(str(rechazo.value)) > 40 or lote.strip() == ""          # el de la incertidumbre es largo: un texto recortado no pasa (M15)
        ventana.boton_guardar.click()
        assert [c["texto"] for c in dialogos.de("warning")] == [f"No se guardó: {rechazo.value}"]
        assert _sql(bd, "SELECT COUNT(*) FROM calibracion_pelicula") == [(0,)]

    def test_un_error_inesperado_se_traduce_y_su_causa_queda_en_el_registro(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        log = tmp_path / "error_log.txt"
        monkeypatch.setenv("RADQA_ERROR_LOG", str(log))

        def ocupada(*a, **k):
            raise sqlite3.OperationalError("database is locked")
        monkeypatch.setattr(svc(), "guardar", ocupada)
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        llenar_el_encabezado(ventana)
        ventana.boton_guardar.click()
        aviso = dialogos.de("warning")[-1]
        assert aviso["titulo"] == "Base de datos ocupada" and "database is locked" not in aviso["texto"]
        assert "database is locked" in log.read_text(encoding="utf-8") and QApplication.overrideCursor() is None

    def test_un_numero_mal_escrito_no_llega_al_servicio(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        llamadas = []
        monkeypatch.setattr(svc(), "guardar", lambda *a, **k: llamadas.append(a))
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        llenar_el_encabezado(ventana)
        ventana.profundidad.setText("tres")
        ventana.boton_guardar.click()
        assert [c["texto"] for c in dialogos.de("warning")] == ["No se guardó: la profundidad no es un número: 'tres'."] and llamadas == []

    def test_los_opcionales_vacios_van_como_nada_y_los_numeros_como_numeros(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        llamadas = []
        monkeypatch.setattr(svc(), "guardar", lambda usuario, encabezado, piezas, virgen=None: llamadas.append((usuario, encabezado, piezas, virgen)) or 1)
        monkeypatch.setattr(ventana_mod().VentanaCurvaDosis, "abrir", lambda self, i: True)
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        ventana.lote.setText("L-02")
        ventana.dfs.setText("100,0")
        ventana.boton_guardar.click()
        usuario, encabezado, piezas, virgen = llamadas[0]
        assert usuario == USUARIO and virgen is None
        assert encabezado == {"lote": "L-02", "tipo_pelicula": "EBT3", "fecha_irradiacion": ventana.fecha_irradiacion.date().toString("yyyy-MM-dd"), "energia": "6 MV", "acelerador": None,
                              "condiciones": {"dfs_cm": 100.0}, "camara": None, "electrometro": None, "u_dosis_medida_pct": None, "escaner_declarado": None, "modo_de_escaneo": None,
                              "observaciones": None}
        assert [type(p["dosis_nominal_cgy"]) for p in piezas] == [float] * 11 and [p["orden"] for p in piezas] == list(range(1, 12))

    def test_la_camara_y_el_electrometro_van_con_su_copia_y_su_puntero(self, ventana, dialogos, tmp_path, escaneos):
        id_ = guardada(ventana, dialogos, tmp_path, escaneos)
        r = svc().leer(id_)
        assert (r["camara_modelo"], r["camara_serie"], r["camara_factor"], r["camara_equipo_id"]) == ("FC65-G", "1234", 4.85e-2, 19)
        assert (r["electrometro_modelo"], r["electrometro_serie"], r["electrometro_factor"], r["electrometro_equipo_id"]) == ("Dose 1", "5678", None, 31)

    def test_la_virgen_montada_se_ve_y_su_copia_se_guarda(self, fabrica, dialogos, tmp_path, escaneos, bd):
        datos = _virgen_sintetica(1)
        referencia = pel().piso_de_pelicula_virgen(datos, _P(), "virgen_lote.tif", fecha_calculo="2026-03-15")
        assert referencia.estado == "ok"
        pel().guardar_referencia_virgen(referencia, os.path.dirname(bd), datos, USUARIO)
        v = fabrica()
        assert "«virgen_lote.tif»" in v.etiqueta_virgen.text()
        id_ = guardada(v, dialogos, tmp_path, escaneos)
        assert svc().leer(id_)["virgen"] == _json(pel().leer_referencia_virgen(os.path.dirname(bd)).como_dict())


# ===================================================================================================== (5) abrir, anular y nueva

class TestAbrirAnularYNueva:
    def test_abrir_se_ve_y_no_se_edita(self, ventana, dialogos, tmp_path, escaneos):
        guardada(ventana, dialogos, tmp_path, escaneos)
        d = dibujo_mod()
        # CD5-PR-6 (ronda 1 de la revision, 31-10): ANTES miraba 7 de los 15 campos del encabezado y la mutacion que solo quitaba `observaciones` de `_editable` sobrevivia. Ahora: los 15 por su nombre Y un
        # barrido de todo campo de texto, menu o fecha del arbol de la ventana (un campo nuevo que `_editable` olvide cae aqui sin tocar esta lista).
        nombres = ("lote", "tipo_pelicula", "fecha_irradiacion", "hora_irradiacion", "acelerador", "energia", "profundidad", "dfs", "campo", "camara", "electrometro", "u_dosis", "escaner", "modo",
                   "observaciones")
        campos = [getattr(ventana, n) for n in nombres]
        barridos = [w for w in recorrer(ventana) if isinstance(w, (QLineEdit, QComboBox, QDateEdit))]
        assert all(any(c is b for b in barridos) for c in campos), "el barrido no ve alguno de los 15 campos del encabezado"
        assert [n for n in nombres if getattr(ventana, n).isEnabled()] == [] and [w for w in barridos if w.isEnabled()] == [] and not ventana.boton_agregar.isEnabled()
        t = ventana.tabla_piezas
        assert not any(t.item(r, c).flags() & Qt.ItemIsEditable for r in range(t.rowCount()) for c in (d.COLUMNA_NOMINAL, d.COLUMNA_MEDIDA))
        assert not any(t.cellWidget(r, c).isEnabled() for r in range(t.rowCount()) for c in (d.COLUMNA_CARGAR, d.COLUMNA_QUITAR))
        antes = copy.deepcopy([{k: v for k, v in f.items() if k != "medida"} for f in ventana._filas])
        escribir(ventana, 3, d.COLUMNA_MEDIDA, "999")
        assert [{k: v for k, v in f.items() if k != "medida"} for f in ventana._filas] == antes

    def test_abrir_dibuja_la_copia_guardada_y_los_equipos_de_su_copia(self, ventana, dialogos, tmp_path, escaneos, catalogo):
        id_ = guardada(ventana, dialogos, tmp_path, escaneos)
        catalogo["Cámara de ionización"]["FC65-G"] = [(19, "9999", "2026-10-01", 9.9)]          # el catálogo cambió después de guardar
        ventana.abrir(id_)
        registro = svc().leer(id_)
        assert _json(ventana._curva.como_dict()) == registro["ajuste"]
        assert ventana.camara.currentText() == "FC65-G 1234 (factor 0.0485; copia guardada)"
        assert [f[7] for f in celdas(ventana.tabla_curva)] == [registro["estado"][c] for c in CAPAS]

    def test_abrir_dice_aparte_los_escaneos_que_faltan_y_las_copias_que_no_coinciden(self, ventana, dialogos, tmp_path, escaneos, bd):
        id_ = guardada(ventana, dialogos, tmp_path, escaneos)
        carpeta = Path(bd).parent / CARPETA
        filas = {f["orden"]: f for f in svc().leer(id_)["piezas"]}
        falta = next(p.name for p in carpeta.iterdir() if p.name.startswith(filas[3]["sha256"]))
        cambia = next(p.name for p in carpeta.iterdir() if p.name.startswith(filas[5]["sha256"]))
        (carpeta / falta).unlink()
        (carpeta / cambia).write_bytes(b"otro contenido")
        ventana.abrir(id_)
        lineas = ventana.etiqueta_registro.text().split("\n")
        assert [l for l in lineas if l.startswith("Faltan junto a la base")] == [f"Faltan junto a la base los escaneos de 1 piezas (lo medido guardado se recalcula igual; volver a medirlas los necesita): {falta}."]
        assert [l for l in lineas if l.startswith("Estas copias")] == [f"Estas copias de los escaneos ya no coinciden con su huella (no son los escaneos que se midieron): {cambia}."]

    def test_abrir_por_la_lista(self, ventana, dialogos, tmp_path, escaneos):
        # CD5-PR-2 (ronda 1 de la revision, 31-10): ANTES guardaba UNA sola calibracion y no distinguia cual se abre (`lista[0]` sobrevivia). Ahora son tres y se elige la del MEDIO: ni la primera ni la ultima.
        ids = []
        for lote in ("L-01", "L-02", "L-03"):
            ventana.boton_nueva.click()
            cargar_todas(ventana, dialogos, tmp_path, escaneos)
            llenar_el_encabezado(ventana, lote=lote)
            ventana.fecha_irradiacion.setDate(QDate(2026, 10, 20))
            ventana.boton_guardar.click()
            assert ventana.estado == "registro", [c["texto"] for c in dialogos.llamadas]
            ids.append(ventana._registro["id"])
        ventana.boton_nueva.click()
        lista = svc().listar()
        assert [f["id"] for f in lista] == ids[::-1]                                  # la mas reciente primero
        textos = [dibujo_mod().texto_de_una_calibracion(f) for f in lista]
        dialogos.elegido = textos[1]
        ventana.boton_abrir.click()
        assert ventana.estado == "registro" and ventana._registro["id"] == ids[1] and dialogos.de("elegir")

    def test_sin_permiso_no_se_anula(self, ventana, dialogos, tmp_path, escaneos, bd, monkeypatch):
        guardada(ventana, dialogos, tmp_path, escaneos)
        llamadas = []
        monkeypatch.setattr(svc(), "anular", lambda *a, **k: llamadas.append(a))
        dialogos.permiso = QDialog.DialogCode.Rejected
        ventana.boton_anular.click()
        assert llamadas == [] and _sql(bd, "SELECT activo FROM calibracion_pelicula") == [(1,)] and dialogos.de("permiso")

    def test_nueva_deja_la_ventana_como_recien_creada(self, fabrica, dialogos, tmp_path, escaneos):
        recien = huella(fabrica())
        v = fabrica()
        guardada(v, dialogos, tmp_path, escaneos)
        v.boton_nueva.click()
        assert huella(v) == recien
        cargar_todas(v, dialogos, tmp_path, escaneos, cuales={1, 2, 3})
        v.boton_agregar.click()
        dialogos.respuesta = QMessageBox.Yes
        v.boton_nueva.click()
        assert huella(v) == recien


# ===================================================================================================== (6) estructura: sin SQL, sin Qt en el dibujo, el empaquetado, sin símbolos

def _arbol(ruta):
    return ast.parse(ruta.read_text(encoding="utf-8"))


SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|PRAGMA)\b.*\b(FROM|INTO|SET|TABLE|WHERE)\b|\bPRAGMA\b", re.IGNORECASE | re.DOTALL)


class TestEstructura:
    @pytest.mark.parametrize("ruta", [VENTANA_PY, DIBUJO_PY], ids=["ventana", "dibujo"])
    def test_sin_sql(self, ruta):
        arbol = _arbol(ruta)
        importados = {a.name.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
        importados |= {(n.module or "").split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
        assert not importados & {"sqlite3", "sqlalchemy"} and not any("QtSql" in (getattr(n, "module", "") or "") for n in ast.walk(arbol))
        llamadas = {n.func.attr for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        assert not llamadas & {"execute", "executemany", "executescript", "cursor", "commit"}
        textos = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        assert not [t for t in textos if SQL.search(t)]

    def test_el_dibujo_no_importa_qt_ni_pyplot(self):
        arbol = _arbol(DIBUJO_PY)
        modulos = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names} | {n.module or "" for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
        assert not [m for m in modulos if m.startswith(("PyQt5", "matplotlib.pyplot"))] and "matplotlib.pyplot" not in DIBUJO_PY.read_text(encoding="utf-8")

    def test_los_cuatro_modulos_estan_en_hidden_imports(self):
        arbol = _arbol(BUILD_PY)
        lista = next(n.value for n in arbol.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "hidden_imports" for t in n.targets))
        nombres = [e.value for e in lista.elts]
        for modulo in ("analisisImagenes.curva_dosis", "analisisImagenes.dibujo_curva_dosis", "services.curva_dosis", "ui.paginasControles.PruebasMensuales.curva_dosis"):
            assert nombres.count(modulo) == 1, modulo

    def test_el_selector_es_el_de_la_ventana_mensual_sin_otra_copia(self):
        mensual = importlib.import_module("ui.paginasControles.PruebasMensuales.placa_mensual")
        assert ventana_mod()._SelectorSinRueda is mensual._SelectorSinRueda
        assert not [n for n in ast.walk(_arbol(VENTANA_PY)) if isinstance(n, ast.ClassDef) and n.name == "_SelectorSinRueda"]

    def test_la_ventana_se_importa_de_forma_estatica(self):
        for ruta in (VENTANA_PY, DIBUJO_PY):
            texto = ruta.read_text(encoding="utf-8")
            assert "importlib" not in texto and "__import__" not in texto

    def test_sin_simbolos_y_con_las_unidades_entre_corchetes(self, ventana, dialogos, tmp_path, escaneos_con_el_rojo_recortado):
        cargar_todas(ventana, dialogos, tmp_path, escaneos_con_el_rojo_recortado)
        textos = []
        for w in recorrer(ventana):
            if isinstance(w, (QLabel, QPushButton)):
                textos += [w.text(), w.toolTip()]
            elif isinstance(w, QLineEdit):
                textos += [w.placeholderText()]
            elif isinstance(w, QComboBox):
                textos += [w.itemText(i) for i in range(w.count())]
            elif isinstance(w, QTableWidget):
                textos += [w.horizontalHeaderItem(c).text() for c in range(w.columnCount())] + [t for f in celdas(w) for t in f if t]
        textos += [t.get_text() for t in ventana.figura.findobj(lambda a: hasattr(a, "get_text") and callable(a.get_text))]
        textos = [t for t in textos if t]
        assert textos and all(sin_simbolos(t) for t in textos)
        assert not [t for t in textos if UNIDAD_ENTRE_PARENTESIS.search(t)]
        assert ventana.eje_curva.get_xlabel() == "densidad óptica neta [1]" and ventana.eje_curva.get_ylabel() == "dosis [cGy]"


# ===================================================================================================== (7) los textos del dibujo, sin Qt

class TestLosTextos:
    def test_un_valor_raro_del_usuario_no_tumba_la_pantalla(self):
        d = dibujo_mod()

        class Raro:
            def __str__(self):
                raise TypeError("no")
        assert d.texto_seguro(10 ** 5000) == "no legible" and d.texto_seguro(Raro()) == "no legible" and d.texto_seguro(None) == "" and d.texto_seguro(3.0) == "3"

    @pytest.mark.parametrize("texto, esperado", [("", (None, None)), ("  ", (None, None)), ("1,5", (1.5, None)), ("100", (100.0, None)), ("abc", (None, "no es un número: 'abc'")),
                                                 ("inf", (None, "no es un número finito: 'inf'")), ("nan", (None, "no es un número finito: 'nan'"))])
    def test_leer_un_numero(self, texto, esperado):
        assert dibujo_mod().leer_numero(texto) == esperado


# ===================================================================================================== (8) AMPLIACIÓN DEL IMPLEMENTADOR (31-10): lo que la cobertura de líneas mostró sin prueba

class TestLaTablaDePiezas:
    def test_quitar_una_fila_la_saca_y_la_curva_se_vuelve_a_ajustar(self, ventana, dialogos, tmp_path, escaneos):
        d = dibujo_mod()
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        _boton(ventana, 4, d.COLUMNA_QUITAR).click()                                  # la fila de 200 cGy
        assert [f[d.COLUMNA_NOMINAL] for f in celdas(ventana.tabla_piezas)] == [f"{x:g}" for x in PLANTILLA if x != 200]
        restantes = {(o if o < 5 else o - 1): v for o, v in escaneos.items() if o != 5}          # el orden de una pieza es el de su fila
        assert [p.orden for p in ventana._curva.piezas] == list(range(1, 11))
        assert _json(ventana._curva.como_dict()) == _json(la_curva_del_motor(restantes, u=None).como_dict())

    def test_quitar_y_cargar_no_hacen_nada_fuera_de_una_calibracion_nueva_o_de_una_fila(self, ventana, dialogos, tmp_path, escaneos):
        assert ventana.cargar_pieza(99, escaneos[2][2], "50.tif") is False and ventana.cargar_pieza(-1, escaneos[2][2], "50.tif") is False
        guardada(ventana, dialogos, tmp_path, escaneos)
        antes = huella(ventana)
        ventana._al_quitar(0)
        assert ventana.cargar_pieza(0, escaneos[2][2], "50.tif") is False
        assert huella(ventana) == antes and not dialogos.de("critical")

    def test_agregar_dosis_agrega_una_fila_y_se_aceptan_replicas(self, ventana, dialogos, tmp_path, escaneos):
        d = dibujo_mod()
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        ventana.boton_agregar.click()
        assert ventana.tabla_piezas.rowCount() == 12
        nueva = celdas(ventana.tabla_piezas)[11]
        assert nueva[d.COLUMNA_NOMINAL] == "" and nueva[d.COLUMNA_ARCHIVO] == "sin imagen" and ventana.tabla_piezas.item(11, d.COLUMNA_NOMINAL).flags() & Qt.ItemIsEditable
        escribir(ventana, 11, d.COLUMNA_NOMINAL, "100")
        cargar(ventana, dialogos, tmp_path, 11, "100_replica.tif", gen.pieza_de_dosis(100, DEVIC, lado_mm=GRANDE, semilla=99).datos)
        escribir(ventana, 11, d.COLUMNA_MEDIDA, "100")
        piezas, problemas = ventana.piezas()
        assert problemas == [] and [p["orden"] for p in piezas] == list(range(1, 13)) and [p["dosis_nominal_cgy"] for p in piezas].count(100.0) == 2
        assert [p.orden for p in ventana._curva.piezas] == list(range(1, 13)) and [ventana._curva.estado(c) for c in CAPAS] == [VALIDA] * 4

    def test_editar_la_dosis_nominal_cambia_la_fila_la_curva_y_lo_que_se_manda_al_servicio(self, ventana, dialogos, tmp_path, escaneos):
        d = dibujo_mod()
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        escribir(ventana, 2, d.COLUMNA_NOMINAL, "110")                                # la fila de 100 cGy
        assert ventana._filas[2]["nominal"] == "110" and ventana._pieza_de_la_curva(3).dosis_nominal_cgy == 110.0
        piezas, problemas = ventana.piezas()
        assert problemas == [] and piezas[2]["dosis_nominal_cgy"] == 110.0 and piezas[2]["dosis_medida_cgy"] == 100.0
        escribir(ventana, 0, d.COLUMNA_NOMINAL, "20")                                 # la de 0 cGy ya no es de 0 cGy: el cero sale de la pieza de menor dosis (guía)
        assert ventana._curva.cero["fuente"] == "pieza_de_menor_dosis"

    def test_editar_una_celda_con_el_editor_de_qt_ajusta_la_curva(self, ventana, dialogos, tmp_path, escaneos):
        d = dibujo_mod()
        ventana.show()
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        editar_con_el_editor(ventana, 2, d.COLUMNA_MEDIDA, "101,5")
        assert ventana._filas[2]["medida_texto"] == "101,5" and ventana._pieza_de_la_curva(3).dosis_medida_cgy == 101.5
        editar_con_el_editor(ventana, 2, d.COLUMNA_NOMINAL, "110")
        assert ventana._filas[2]["nominal"] == "110" and ventana._pieza_de_la_curva(3).dosis_nominal_cgy == 110.0
        assert celdas(ventana.tabla_piezas)[2][d.COLUMNA_MEDIDA] == "101,5" and not dialogos.de("critical")

    def test_una_dosis_que_no_es_un_numero_no_entra_en_la_curva_ni_llega_al_servicio(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        d = dibujo_mod()
        llamadas = []
        monkeypatch.setattr(svc(), "guardar", lambda *a, **k: llamadas.append(a))
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        llenar_el_encabezado(ventana)
        escribir(ventana, 3, d.COLUMNA_MEDIDA, "abc")                                 # la fila de 150 cGy
        assert ventana._pieza_de_la_curva(4) is None and len(ventana._curva.piezas) == 10
        lineas = ventana.etiqueta_curva.text().split("\n")
        assert "No entra en la curva: la dosis medida de la fila 4 no es un número: 'abc'." in lineas
        escribir(ventana, 5, d.COLUMNA_NOMINAL, "-3")                                 # la fila de 300 cGy
        assert "No entra en la curva: la dosis nominal de la fila 6 debe ser un número de 0 o más." in ventana.etiqueta_curva.text().split("\n")
        escribir(ventana, 6, d.COLUMNA_NOMINAL, "")                                   # la fila de 400 cGy
        ventana.boton_guardar.click()
        assert [c["texto"] for c in dialogos.de("warning")] == ["No se guardó: la dosis medida de la fila 4 no es un número: 'abc'; la dosis nominal de la fila 7 falta."] and llamadas == []

    def test_una_unica_pieza_con_la_dosis_mal_escrita_deja_la_pantalla_sin_curva(self, ventana, dialogos, tmp_path, escaneos):
        d = dibujo_mod()
        cargar(ventana, dialogos, tmp_path, 1, "50.tif", escaneos[2][2])
        assert ventana._curva is not None                                             # con la dosis medida vacía la pieza entra y la curva queda incompleta
        escribir(ventana, 1, d.COLUMNA_MEDIDA, "abc")
        assert ventana._curva is None and ventana.boton_guardar.isEnabled()
        assert [celdas(ventana.tabla_piezas)[1][d.COLUMNA_DE_LA_CAPA[c]] for c in CAPAS] == [""] * 4
        assert "No entra en la curva: la dosis medida de la fila 2 no es un número: 'abc'." in ventana.etiqueta_curva.text().split("\n")

    def test_una_incertidumbre_que_no_es_un_numero_no_entra_en_la_curva_ni_llega_al_servicio(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        llamadas = []
        monkeypatch.setattr(svc(), "guardar", lambda *a, **k: llamadas.append(a))
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        llenar_el_encabezado(ventana)
        ventana.u_dosis.setText("mucha")
        assert "No entra en la curva: la incertidumbre de la dosis medida no es un número: 'mucha'." in ventana.etiqueta_curva.text().split("\n")
        ventana.boton_guardar.click()
        assert [c["texto"] for c in dialogos.de("warning")] == ["No se guardó: la incertidumbre de la dosis medida no es un número: 'mucha'."] and llamadas == []

    def test_cargar_imagen_cancelado_o_con_un_archivo_ilegible_no_cambia_la_fila(self, ventana, dialogos, tmp_path):
        d = dibujo_mod()
        antes = huella(ventana)
        dialogos.ruta = ""
        _boton(ventana, 1, d.COLUMNA_CARGAR).click()
        assert dialogos.llamadas == [] and huella(ventana) == antes
        dialogos.ruta = str(tmp_path / "no_existe.tif")
        _boton(ventana, 1, d.COLUMNA_CARGAR).click()
        avisos = dialogos.de("warning")
        assert len(avisos) == 1 and avisos[0]["texto"].startswith("No se pudo leer el archivo: ") and huella(ventana) == antes

    def test_el_indicador_se_ve_mientras_mide_y_mientras_guarda_y_se_esconde_despues(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        vistos = []
        medir, guardar = pel().medir_pieza_uniforme, svc().guardar
        monkeypatch.setattr(pel(), "medir_pieza_uniforme", lambda *a, **k: vistos.append(("mide", ventana.indicador.isVisibleTo(ventana), ventana.indicador.text())) or medir(*a, **k))
        monkeypatch.setattr(svc(), "guardar", lambda *a, **k: vistos.append(("guarda", ventana.indicador.isVisibleTo(ventana), ventana.indicador.text())) or guardar(*a, **k))
        cargar_todas(ventana, dialogos, tmp_path, escaneos, cuales={1, 2, 3})
        assert vistos == [("mide", True, ventana_mod().TEXTO_MIDIENDO)] * 3 and not ventana.indicador.isVisibleTo(ventana)
        llenar_el_encabezado(ventana)
        ventana.boton_guardar.click()
        assert vistos[3:] == [("guarda", True, ventana_mod().TEXTO_GUARDANDO)] and not ventana.indicador.isVisibleTo(ventana) and ventana.estado == "registro"

    def test_una_fila_con_un_escaneo_de_mas_de_20_mb_lo_avisa(self, ventana, escaneos, monkeypatch):
        medida = pel().medir_pieza_uniforme(escaneos[2][2], _P(), "50.tif", "2026-10-30", escala="declarada")
        monkeypatch.setattr(pel(), "medir_pieza_uniforme", lambda *a, **k: medida)
        assert ventana.cargar_pieza(1, b"\0" * 21_000_000, "grande.tif") is True
        assert celdas(ventana.tabla_piezas)[1][dibujo_mod().COLUMNA_ARCHIVO] == "grande.tif: el archivo pesa 21.0 [MB], conviene escanear solo el área de la pieza"


class TestElEncabezadoYLosEquipos:
    def test_todo_el_encabezado_se_guarda_y_se_vuelve_a_ver(self, ventana, dialogos, tmp_path, escaneos):
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        ventana.lote.setText("  L-77  ")
        ventana.tipo_pelicula.setEditText("EBT-XD")
        ventana.fecha_irradiacion.setDate(QDate(2026, 10, 20))
        ventana.hora_irradiacion.setText("9:5")
        ventana.acelerador.setCurrentIndex(2)
        ventana.energia.setEditText("9 MeV")
        ventana.profundidad.setText("3,5")
        ventana.dfs.setText("100")
        ventana.campo.setText(" 10 × 10 ")
        ventana.camara.setCurrentIndex(1)
        ventana.electrometro.setCurrentIndex(1)
        ventana.u_dosis.setText("1,5")
        ventana.escaner.setText("Epson WF-6590")
        ventana.modo.setCurrentIndex(1)
        ventana.observaciones.setText("mesa a 0 grados")
        ventana.boton_guardar.click()
        assert ventana.estado == "registro", [c["texto"] for c in dialogos.llamadas]
        r = svc().leer(ventana._registro["id"])
        assert (r["lote"], r["tipo_pelicula"], r["fecha_irradiacion"], r["acelerador"], r["energia"], r["observaciones"]) == ("L-77", "EBT-XD", "2026-10-20", "Clinac iX", "9 MeV", "mesa a 0 grados")
        assert r["condiciones"] == {"profundidad_cm": 3.5, "dfs_cm": 100.0, "campo_cm": "10 × 10", "hora_irradiacion": "09:05"} and r["u_dosis_medida_pct"] == 1.5
        assert (r["cadena_de_captura"]["escaner_declarado"], r["cadena_de_captura"]["modo_de_escaneo"]) == ("Epson WF-6590", "transmisión")
        assert (ventana.lote.text(), ventana.tipo_pelicula.currentText(), ventana.fecha_irradiacion.date().toString("yyyy-MM-dd"), ventana.hora_irradiacion.text(), ventana.acelerador.currentText(),
                ventana.energia.currentText(), ventana.profundidad.text(), ventana.dfs.text(), ventana.campo.text(), ventana.u_dosis.text(), ventana.escaner.text(), ventana.modo.currentData(),
                ventana.observaciones.text()) == ("L-77", "EBT-XD", "2026-10-20", "09:05", "Clinac iX", "9 MeV", "3.5", "100", "10 × 10", "1.5", "Epson WF-6590", "transmisión", "mesa a 0 grados")

    @pytest.mark.parametrize("escrita, esperada", [("9:5", "09:05"), ("00:00", "00:00"), ("23:59", "23:59"), (" 7:05 ", "07:05")])
    def test_la_hora_se_guarda_como_hh_mm(self, ventana, escrita, esperada):
        ventana.hora_irradiacion.setText(escrita)
        encabezado, problemas = ventana.encabezado()
        assert problemas == [] and encabezado["condiciones"] == {"hora_irradiacion": esperada}

    @pytest.mark.parametrize("escrita", ["24:00", "12:60", "9", "9:", ":30", "ab:cd", "12:30:00", "-1:00"])
    def test_una_hora_mal_escrita_es_un_problema(self, ventana, escrita):
        _encabezado, problemas = ventana.encabezado()
        assert problemas == []
        ventana.hora_irradiacion.setText(escrita)
        _encabezado, problemas = ventana.encabezado()
        assert problemas == [f"la hora de irradiación debe ser hh:mm, no {escrita!r}"]

    def test_una_hora_mal_escrita_no_llega_al_servicio(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        llamadas = []
        monkeypatch.setattr(svc(), "guardar", lambda *a, **k: llamadas.append(a))
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        llenar_el_encabezado(ventana)
        ventana.hora_irradiacion.setText("25:00")
        ventana.boton_guardar.click()
        assert [c["texto"] for c in dialogos.de("warning")] == ["No se guardó: la hora de irradiación debe ser hh:mm, no '25:00'."] and llamadas == []

    def test_un_catalogo_que_no_se_puede_leer_se_dice_y_la_calibracion_se_guarda_sin_equipo(self, fabrica, dialogos, tmp_path, escaneos, monkeypatch):
        from services.equipos_service import EquiposService

        def caido(tipo):
            raise RuntimeError("catálogo caído")
        monkeypatch.setattr(EquiposService, "modelos_actuales", staticmethod(caido))
        v = fabrica()
        assert [v.camara.itemText(i) for i in range(v.camara.count())] == [ventana_mod().SIN_CAMARA]
        assert [v.electrometro.itemText(i) for i in range(v.electrometro.count())] == [ventana_mod().SIN_ELECTROMETRO]
        texto = v.etiqueta_curva.text()
        assert "No se pudo leer el catálogo de equipos (Cámara de ionización): catálogo caído" in texto and "No se pudo leer el catálogo de equipos (Electrómetro): catálogo caído" in texto
        r = svc().leer(guardada(v, dialogos, tmp_path, escaneos))
        assert (r["camara_modelo"], r["camara_equipo_id"], r["electrometro_modelo"], r["electrometro_equipo_id"]) == (None, None, None, None)

    def test_un_equipo_elegido_que_ya_no_esta_en_el_catalogo_no_se_guarda_en_silencio(self, ventana, dialogos, tmp_path, escaneos, catalogo, monkeypatch):
        llamadas = []
        monkeypatch.setattr(svc(), "guardar", lambda *a, **k: llamadas.append(a))
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        llenar_el_encabezado(ventana)                                                 # elige la cámara 19 y el electrómetro 31
        catalogo["Electrómetro"]["Dose 1"] = []                                       # el catálogo cambió entre elegir y guardar
        ventana.boton_guardar.click()
        assert [c["texto"] for c in dialogos.de("warning")] == ["No se guardó: el electrómetro elegido ya no está en el catálogo."] and llamadas == []


class TestLoQueDiceElServicioAlAbrirYAnular:
    def test_abrir_un_id_que_no_existe_o_que_no_cabe_en_la_base_lo_dice_y_no_cambia_la_ventana(self, ventana, dialogos):
        antes = huella(ventana)
        assert ventana.abrir(99999) is False
        with pytest.raises(svc().CurvaDosisError) as rechazo:
            svc().leer(2 ** 70)
        assert ventana.abrir(2 ** 70) is False
        assert [c["texto"] for c in dialogos.de("warning")] == ["No hay ninguna calibración con el id 99999.", f"No se pudo abrir la calibración: {rechazo.value}"]
        assert ventana.estado == "nueva" and huella(ventana) == antes

    def test_abrir_sin_calibraciones_guardadas_lo_dice(self, ventana, dialogos):
        ventana.boton_abrir.click()
        assert [c["texto"] for c in dialogos.de("information")] == ["No hay calibraciones guardadas."] and dialogos.de("elegir") == [] and ventana.estado == "nueva"

    def test_un_recalculo_que_el_servicio_rechaza_se_dice_tal_cual_y_se_ve_la_copia_guardada(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        id_ = guardada(ventana, dialogos, tmp_path, escaneos)
        texto = "lo guardado de la calibración no se puede volver a ajustar: la capa R trae un texto largo que no se recorta ni se traduce"

        def rechaza(registro):
            raise svc().CurvaDosisError(texto)
        monkeypatch.setattr(svc(), "recalcular", rechaza)
        assert ventana.abrir(id_) is True
        assert ventana.estado == "registro" and texto in ventana.etiqueta_registro.text().split("\n")
        assert _json(ventana._curva.como_dict()) == svc().leer(id_)["ajuste"] and dialogos.de("warning") == []

    def test_lo_recalculado_que_no_coincide_con_lo_guardado_se_dice_y_se_avisa(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        id_ = guardada(ventana, dialogos, tmp_path, escaneos)
        monkeypatch.setattr(svc(), "diferencias", lambda registro, recalculo: ["primera diferencia", "segunda diferencia"])
        ventana.abrir(id_)
        assert "Lo recalculado no coincide con lo guardado: primera diferencia; segunda diferencia." in ventana.etiqueta_registro.text().split("\n")
        assert [c["texto"] for c in dialogos.de("warning")] == ["Lo recalculado no coincide con lo guardado:\nprimera diferencia\nsegunda diferencia"]

    def test_anular_lo_que_rechaza_el_servicio_se_dice_tal_cual_y_si_ya_estaba_anulada_tambien(self, ventana, dialogos, tmp_path, escaneos, bd, monkeypatch):
        guardada(ventana, dialogos, tmp_path, escaneos)
        rechazo = "el usuario de la sesión no puede anular calibraciones: " + "x" * 40

        def rechaza(*a, **k):
            raise svc().CurvaDosisError(rechazo)
        monkeypatch.setattr(svc(), "anular", rechaza)
        ventana.boton_anular.click()
        assert [c["texto"] for c in dialogos.de("warning")] == [f"No se anuló: {rechazo}"]
        assert _sql(bd, "SELECT activo FROM calibracion_pelicula") == [(1,)] and ventana.estado == "registro" and ventana.boton_anular.isEnabled()
        monkeypatch.setattr(svc(), "anular", lambda *a, **k: False)
        ventana.boton_anular.click()
        assert [c["texto"] for c in dialogos.de("warning")][1:] == ["Esa calibración ya estaba anulada o ya no existe."] and ventana.estado == "registro"

    def test_la_pregunta_de_anular_va_antes_del_permiso(self, ventana, dialogos, tmp_path, escaneos, bd):
        id_ = guardada(ventana, dialogos, tmp_path, escaneos)
        dialogos.respuesta = QMessageBox.No
        ventana.boton_anular.click()
        preguntas = dialogos.de("question")
        assert len(preguntas) == 1 and preguntas[0]["texto"].startswith(f"¿Anular la calibración {id_} (lote L-01)?")
        assert dialogos.permisos_pedidos == [] and dialogos.de("permiso") == [] and _sql(bd, "SELECT activo FROM calibracion_pelicula") == [(1,)]

    def test_guardar_y_anular_no_hacen_nada_fuera_de_su_estado(self, ventana, dialogos, tmp_path, escaneos, bd):
        ventana._al_anular()                                                          # una calibración nueva no se anula
        assert dialogos.llamadas == []
        guardada(ventana, dialogos, tmp_path, escaneos)
        n = len(dialogos.llamadas)
        ventana._al_guardar()                                                         # una calibración abierta no se guarda otra vez
        assert len(dialogos.llamadas) == n and _sql(bd, "SELECT COUNT(*) FROM calibracion_pelicula") == [(1,)]
        ventana.boton_anular.click()
        n = len(dialogos.llamadas)
        ventana._al_anular()                                                          # una anulada no se anula otra vez
        assert len(dialogos.llamadas) == n and _sql(bd, "SELECT activo FROM calibracion_pelicula") == [(0,)]

    def test_nueva_con_piezas_sin_guardar_pregunta_y_si_se_dice_que_no_las_conserva(self, ventana, dialogos, tmp_path, escaneos):
        ventana.boton_nueva.click()
        assert dialogos.de("question") == []                                          # sin piezas cargadas no pregunta
        cargar_todas(ventana, dialogos, tmp_path, escaneos, cuales={1, 2})
        dialogos.respuesta = QMessageBox.No
        antes = huella(ventana)
        ventana.boton_nueva.click()
        assert [c["texto"] for c in dialogos.de("question")] == [ventana_mod().PREGUNTA_NUEVA]
        assert ventana.estado == "nueva" and ventana._filas[1]["datos"] is not None and huella(ventana) == antes


class TestLaVirgenMontada:
    def test_la_virgen_de_la_misma_cadena_hace_de_cero_si_no_hay_pieza_de_0_cgy(self, fabrica, dialogos, tmp_path, escaneos_a_600_ppp, bd):
        datos, referencia = _virgen_a_600()
        assert referencia.estado == "ok", referencia.estado
        pel().guardar_referencia_virgen(referencia, os.path.dirname(bd), datos, USUARIO)
        v = fabrica()
        cargar_todas(v, dialogos, tmp_path, escaneos_a_600_ppp)
        assert v._curva.cero["fuente"] == "pelicula_virgen" and v._curva.cero["detalle"].startswith("la película virgen montada «virgen.tif»")
        assert v.etiqueta_virgen.text().endswith(": hace de cero de esta curva.") and v.etiqueta_curva.text().startswith(f"Cero de la curva: {v._curva.cero['detalle']}.")
        llenar_el_encabezado(v)
        dialogos.respuesta = QMessageBox.No
        v.boton_guardar.click()
        assert f"La curva no tiene una pieza de 0 cGy: {v._curva.cero['detalle']}." in dialogos.de("question")[0]["texto"] and v.estado == "nueva"
        dialogos.respuesta = QMessageBox.Yes
        v.boton_guardar.click()
        r = svc().leer(v._registro["id"])
        assert r["cero"]["fuente"] == "pelicula_virgen" and r["virgen"] == _json(pel().leer_referencia_virgen(os.path.dirname(bd)).como_dict())

    def test_una_virgen_que_no_se_puede_leer_se_dice_y_la_curva_se_ajusta_sin_ella(self, fabrica, monkeypatch):
        def rota(carpeta):
            raise ValueError("el archivo de la virgen está dañado")
        monkeypatch.setattr(pel(), "leer_referencia_virgen", rota)
        v = fabrica()
        assert v.etiqueta_virgen.text() == "Película virgen montada: no se pudo leer (el archivo de la virgen está dañado); la curva se ajusta sin ella." and v._virgen_utilizable() is None

    @pytest.mark.parametrize("referencia, aviso, cero, avisos, esperado", [
        (None, "daño", None, (), "Película virgen montada: no se pudo leer (daño); la curva se ajusta sin ella."),
        (None, "", None, (), "Película virgen montada: no hay ninguna junto a la base; el cero sale de las piezas."),
        ({"estado": "no válida: ruido"}, "", None, (), "Película virgen montada: «v.tif» (2026-03-15): no es válida (no válida: ruido) y no se usa."),
        ({"estado": "ok"}, "", None, (), "Película virgen montada: «v.tif» (2026-03-15): se usará como cero si no hay piezas de 0 cGy y su cadena de captura es la de las piezas."),
        ({"estado": "ok"}, "", "pelicula_virgen", (), "Película virgen montada: «v.tif» (2026-03-15): hace de cero de esta curva."),
        ({"estado": "ok"}, "", "pieza_de_menor_dosis", ("OTRA",), "Película virgen montada: «v.tif» (2026-03-15): la película virgen montada no sirve de cero: se escaneó con otra cadena."),
        ({"estado": "ok"}, "", "piezas_de_0_cgy", (), "Película virgen montada: «v.tif» (2026-03-15): no hace de cero, porque hay piezas de 0 cGy; se guarda su copia con la calibración."),
        ({"estado": "ok"}, "", "pieza_de_menor_dosis", (), "Película virgen montada: «v.tif» (2026-03-15): no hace de cero; se guarda su copia con la calibración."),
        ({"estado": "ok", "procedencia": {"fecha_calculo": "2026-10-30"}}, "", None, (), "Película virgen montada: «sin nombre» (2026-10-30): se usará como cero si no hay piezas de 0 cGy y su cadena de captura es la de las piezas."),
        ({"estado": "ok", "procedencia": None}, "", None, (), "Película virgen montada: «sin nombre» (sin fecha): se usará como cero si no hay piezas de 0 cGy y su cadena de captura es la de las piezas."),
    ], ids=["no_se_pudo_leer", "ninguna", "no_valida", "sin_curva", "hace_de_cero", "no_sirve_de_cero", "hay_piezas_de_0", "no_hace_de_cero", "sin_nombre_con_fecha_de_calculo", "sin_nombre_ni_fecha"])
    def test_el_texto_de_la_virgen_segun_el_caso(self, referencia, aviso, cero, avisos, esperado):
        if referencia is not None:
            referencia = SimpleNamespace(**{"procedencia": {"archivo": "v.tif", "fecha_escaneo": "2026-03-15"}, **referencia})
        curva = None if cero is None else SimpleNamespace(cero={"fuente": cero}, avisos=[motor().AVISO_VIRGEN_NO_SIRVE.format(motivo="se escaneó con otra cadena") for _a in avisos])
        assert dibujo_mod().texto_de_la_virgen(referencia, aviso, curva) == esperado


class TestLosTextosDelDibujoAmpliados:
    @pytest.mark.parametrize("tamano, avisa", [(20_000_000, False), (20_000_001, True)])
    def test_el_aviso_de_dc14_es_solo_para_los_escaneos_de_mas_de_20_mb(self, tamano, avisa):
        texto = dibujo_mod().texto_del_archivo("grande.tif", b"\0" * tamano, 50.0)
        assert texto == ("grande.tif: el archivo pesa 20.0 [MB], conviene escanear solo el área de la pieza" if avisa else "grande.tif")

    def test_un_booleano_se_escribe_si_o_no_y_sin_calibracion_abierta_no_hay_lineas_de_la_carpeta(self):
        d = dibujo_mod()
        assert d.texto_seguro(True) == "sí" and d.texto_seguro(False) == "no" and d.texto_de_la_carpeta(None) == []


# ===================================================================================================== (9) CORRECCIÓN DE LA RONDA 1 DE LA REVISIÓN ESCÉPTICA (corrector, 31-10-2026)
#
# Los 16 hallazgos (14 defectos distintos) que la revisión reprodujo y el corrector volvió a reproducir (logs/CD5/ronda1_correccion/repro/): de producción CD5-PROD-R1-01, 02, 05, 07, 08, 09 y CD5-PR-7 (cada prueba CAYÓ contra el árbol
# sin corregir, por su razón: logs/CD5/ronda1_correccion/rojo.log) y de pruebas débiles CD5-PROD-R1-03, 04, 06 y CD5-PR-1 a 6 (la producción estaba bien: cada prueba pasa y la mutación que sobrevivía
# ahora cae, `cd5_mutaciones.py` Y10 en adelante).

FECHA = QDate(2026, 10, 20)


def _cargar_las_irradiadas_sin_dosis_medida(v, dialogos, tmp_path, escaneos):
    """Las diez piezas irradiadas de la plantilla (sin la de 0 cGy), cada una con su imagen y SIN escribir su dosis medida: todas se miden y la curva no puede tener cero."""
    for orden, (dosis, nombre, datos) in sorted(escaneos.items()):
        if dosis > 0:
            cargar(v, dialogos, tmp_path, orden - 1, nombre, datos)


def _guardar_con(v, dialogos, tmp_path, escaneos, lote="L-01", energia="6 MV", fecha=FECHA, **k):
    """Carga las piezas, llena el encabezado con ese lote, esa energía y esa fecha y pulsa «Guardar» (el resultado lo comprueba quien llama)."""
    cargar_todas(v, dialogos, tmp_path, escaneos, **k)
    llenar_el_encabezado(v, lote=lote)
    v.energia.setEditText(energia)
    v.fecha_irradiacion.setDate(fecha)
    v.boton_guardar.click()


class TestLaCurvaSinCero:
    """CD5-PROD-R1-01 y CD5-PROD-R1-05: una curva se queda sin cero por más de una causa (ninguna pieza medible, o piezas bien medidas sin pieza de 0 cGy ni virgen y sin la dosis medida de la de menor dosis), y ni
    el aviso de «Guardar» ni la celda de una pieza pueden decir siempre la primera."""

    def test_con_las_piezas_medidas_pero_sin_dosis_medida_el_aviso_dice_lo_que_falta_y_no_que_ninguna_se_midio(self, ventana, dialogos, tmp_path, escaneos, bd):
        d = dibujo_mod()
        _cargar_las_irradiadas_sin_dosis_medida(ventana, dialogos, tmp_path, escaneos)
        llenar_el_encabezado(ventana)
        assert len(ventana._curva.piezas) == 10 and all(p.estado == "ok" for p in ventana._curva.piezas) and ventana._curva.cero is None          # la premisa: todas se midieron y aun así no hay cero
        ventana.boton_guardar.click()
        avisos = [c["texto"] for c in dialogos.de("warning")]
        assert avisos == [ventana_mod().NO_GUARDA_SIN_CERO] and _sql(bd, "SELECT COUNT(*) FROM calibracion_pelicula") == [(0,)]
        assert "ninguna pieza se pudo medir" not in avisos[0] and "dosis medida" in avisos[0] and "película virgen" in avisos[0]
        escribir(ventana, 1, d.COLUMNA_MEDIDA, "50")                                  # el remedio que dice el aviso: la dosis medida de la pieza irradiada de menor dosis
        assert ventana._curva.cero["fuente"] == "pieza_de_menor_dosis"

    def test_sin_cero_la_celda_de_una_pieza_que_se_midio_bien_dice_que_falta_el_cero_y_no_que_no_es_medible(self, ventana, dialogos, tmp_path, escaneos):
        d = dibujo_mod()
        cargar(ventana, dialogos, tmp_path, 2, escaneos[3][1], escaneos[3][2])        # la de 100 cGy, sola: la curva todavía no tiene cero
        assert ventana._curva.cero is None and ventana._pieza_de_la_curva(3).estado == "ok"
        sin_cero = [celdas(ventana.tabla_piezas)[2][d.COLUMNA_DE_LA_CAPA[c]] for c in CAPAS]
        assert sin_cero != [d.NO_MEDIBLE] * 4, "una pieza que se midió bien dice «no medible» solo porque la curva todavía no tiene cero"
        assert sin_cero == [d.SIN_CERO] * 4 and d.SIN_CERO != d.NO_MEDIBLE and "cero" in d.SIN_CERO
        cargar(ventana, dialogos, tmp_path, 0, escaneos[1][1], escaneos[1][2])        # la película virgen (0 cGy): ahora hay cero y la misma fila da su netOD
        assert all(re.fullmatch(r"\d\.\d{4} ± \d\.\d{4}", celdas(ventana.tabla_piezas)[2][d.COLUMNA_DE_LA_CAPA[c]]) for c in CAPAS)


class TestGuardarEncimaDeUnaVigente:
    """CD5-PROD-R1-02: guardar con el mismo lote, la misma fecha y la misma energía anula la calibración vigente (CD.4); la ventana lo pregunta ANTES (como las diarias, DA-41, y como la ventana mensual)."""

    def test_pregunta_antes_de_reemplazar_a_la_vigente_y_si_se_dice_que_no_no_toca_nada(self, ventana, dialogos, tmp_path, escaneos, bd):
        _guardar_con(ventana, dialogos, tmp_path, escaneos)
        primera = ventana._registro["id"]
        assert dialogos.de("question") == []                                          # la primera no reemplaza nada: no pregunta
        ventana.boton_nueva.click()
        dialogos.respuesta = QMessageBox.No
        _guardar_con(ventana, dialogos, tmp_path, escaneos)
        preguntas = dialogos.de("question")
        assert len(preguntas) == 1 and "REEMPLAZA" in preguntas[0]["texto"] and f"id {primera}" in preguntas[0]["texto"] and preguntas[0]["texto"].endswith(ventana_mod().PREGUNTA_GUARDAR)
        assert _sql(bd, "SELECT id, activo FROM calibracion_pelicula ORDER BY id") == [(primera, 1)] and ventana.estado == "nueva"
        dialogos.respuesta = QMessageBox.Yes
        ventana.boton_guardar.click()
        assert _sql(bd, "SELECT id, activo FROM calibracion_pelicula ORDER BY id") == [(primera, 0), (primera + 1, 1)] and ventana.estado == "registro"
        assert [a for (a,) in _sql(bd, "SELECT accion FROM audit_log WHERE tabla = 'calibracion_pelicula' ORDER BY id")] == ["guardar", "reemplazo"]

    def test_con_otra_energia_no_pregunta_nada_y_las_dos_quedan_vigentes(self, ventana, dialogos, tmp_path, escaneos, bd):
        _guardar_con(ventana, dialogos, tmp_path, escaneos)
        primera = ventana._registro["id"]
        ventana.boton_nueva.click()
        _guardar_con(ventana, dialogos, tmp_path, escaneos, energia="10 MV")
        assert dialogos.de("question") == [] and ventana.estado == "registro"
        assert _sql(bd, "SELECT id, activo FROM calibracion_pelicula ORDER BY id") == [(primera, 1), (primera + 1, 1)]

    @pytest.mark.parametrize("lote, energia, fecha, reemplaza", [
        ("L-01", "6 MV", "2026-10-20", True), ("  L-01  ", "6 MV", "2026-10-20", True), ("L-02", "6 MV", "2026-10-20", False), ("l-01", "6 MV", "2026-10-20", False),
        ("L-01", "10 MV", "2026-10-20", False), ("L-01", "6 mv", "2026-10-20", False), ("L-01", "6 MV", "2026-10-21", False)],
        ids=["la_misma", "con_espacios", "otro_lote", "mayusculas_del_lote", "otra_energia", "mayusculas_de_la_energia", "otra_fecha"])
    def test_lo_que_la_ventana_anticipa_es_lo_que_el_servicio_hace(self, bd, escaneos, lote, energia, fecha, reemplaza):
        """La convergencia de los dos caminos, con el servicio REAL: la ventana anticipa (`la_calibracion_que_reemplaza`) lo que `guardar` hace con la clave de bloque (`lote`, `DATE(fecha)`, `energia`)."""
        piezas = [{"orden": o, "dosis_nominal_cgy": float(d), "dosis_medida_cgy": float(d), "datos": b, "nombre_archivo": n} for o, (d, n, b) in sorted(escaneos.items()) if o <= 3]
        base = {"lote": "L-01", "tipo_pelicula": "EBT3", "fecha_irradiacion": "2026-10-20", "energia": "6 MV"}
        primera = svc().guardar(USUARIO, base, piezas)
        anticipada = dibujo_mod().la_calibracion_que_reemplaza(svc().listar(), {**base, "lote": lote.strip(), "energia": energia, "fecha_irradiacion": fecha})
        segunda = svc().guardar(USUARIO, {**base, "lote": lote, "energia": energia, "fecha_irradiacion": fecha}, piezas)
        assert (svc().leer(primera)["activo"] == 0) is reemplaza and (anticipada is not None) is reemplaza and svc().leer(segunda)["activo"] == 1
        assert anticipada is None or anticipada["id"] == primera


class TestLaHoraConDigitosQueNoSonDe0A9:
    """CD5-PROD-R1-07: `isdigit` acepta un superíndice o un dígito encerrado en un círculo y `int` los rechaza: la validación de la hora usa el predicado que `int` usa."""

    @pytest.mark.parametrize("escrita", ["1²:30", "12:3²", "①②:30"])
    def test_es_un_problema_que_se_dice_y_no_un_error_inesperado(self, ventana, dialogos, tmp_path, escaneos, escrita):
        ventana.hora_irradiacion.setText(escrita)
        _encabezado, problemas = ventana.encabezado()                                 # antes lanzaba ValueError
        assert problemas == [f"la hora de irradiación debe ser hh:mm, no {escrita!r}"]
        cargar_todas(ventana, dialogos, tmp_path, escaneos, cuales={1, 2, 3, 4})
        llenar_el_encabezado(ventana)
        ventana.boton_guardar.click()
        assert [c["texto"] for c in dialogos.de("warning")] == [f"No se guardó: la hora de irradiación debe ser hh:mm, no {escrita!r}."]


class TestUnErrorInesperadoAlMedirUnaPieza:
    """CD5-PROD-R1-08: la causa (una imagen de 40 píxeles de lado o menos a 300 ppp hace lanzar `ZeroDivisionError` a CD.2, `pelicula.py::_virgen_recorte`) vive fuera de CD.5; la ventana, que solo atrapaba
    `ValueError`, no puede dejar un «Error inesperado» sin pieza y sin causa en `error_log.txt` (el `.exe` no tiene consola)."""

    def test_se_dice_con_el_nombre_de_la_pieza_la_fila_queda_como_estaba_y_la_causa_queda_en_el_registro(self, ventana, dialogos, tmp_path, escaneos, monkeypatch):
        log = tmp_path / "error_log.txt"
        monkeypatch.setenv("RADQA_ERROR_LOG", str(log))

        def rota(*a, **k):
            assert QApplication.overrideCursor() is not None and QApplication.overrideCursor().shape() == Qt.WaitCursor
            raise ZeroDivisionError("float division by zero")
        monkeypatch.setattr(pel(), "medir_pieza_uniforme", rota)
        antes = huella(ventana)
        cargar(ventana, dialogos, tmp_path, 1, "50.tif", escaneos[2][2])
        avisos = [c["texto"] for c in dialogos.de("warning")]
        assert len(avisos) == 1 and avisos[0].startswith("No se pudo medir la pieza «50.tif»: ") and "ZeroDivisionError: float division by zero" in avisos[0] and "error_log.txt" in avisos[0]
        assert dialogos.de("critical") == [] and QApplication.overrideCursor() is None and huella(ventana) == antes
        assert "float division by zero" in log.read_text(encoding="utf-8")

    def test_un_archivo_diminuto_nunca_da_un_error_inesperado(self, ventana, dialogos, tmp_path):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (1, 1), (200, 200, 200)).save(buf, format="TIFF", dpi=(300, 300))
        cargar(ventana, dialogos, tmp_path, 2, "uno.tif", buf.getvalue())
        fila = celdas(ventana.tabla_piezas)[2]
        d = dibujo_mod()
        assert dialogos.de("critical") == [] and QApplication.overrideCursor() is None
        assert dialogos.de("warning") or all(fila[d.COLUMNA_DE_LA_CAPA[c]].startswith("no medible") for c in CAPAS)          # o la ventana avisa, o la fila dice por qué (si CD.2 un día lo mide)


class TestNuevaConLosMenusEditables:
    """CD5-PROD-R1-09: lo que el físico escribe y confirma con Enter en «Tipo de película» o «Energía» entra a la lista del menú (Qt); «Nueva» deja la ventana igual a una recién creada (CD5-D11)."""

    @pytest.mark.parametrize("menu, escrito", [("tipo_pelicula", "EBT2X"), ("energia", "18 MV")])
    def test_nueva_quita_de_la_lista_lo_que_el_fisico_escribio_y_confirmo_con_enter(self, fabrica, menu, escrito):
        recien = huella(fabrica())
        v = fabrica()
        v.show()
        QApplication.processEvents()
        combo = getattr(v, menu)
        combo.lineEdit().selectAll()
        QTest.keyClicks(combo.lineEdit(), escrito)
        QTest.keyClick(combo.lineEdit(), Qt.Key_Return)
        QApplication.processEvents()
        assert escrito in [combo.itemText(i) for i in range(combo.count())]           # la premisa: Qt agrega a la lista lo que se confirma con Enter
        v.boton_nueva.click()
        v.hide()
        QApplication.processEvents()
        assert escrito not in [combo.itemText(i) for i in range(combo.count())] and huella(v) == recien


class TestElFactorDelCatalogo:
    """CD5-PR-7: «factor = calibr_fact del catálogo como número» (plan, CD5-D5): la copia guardada (DA-13) es el número del catálogo, no su texto de seis cifras."""

    def test_el_factor_guardado_es_el_numero_del_catalogo_y_no_su_texto_redondeado(self, ventana, dialogos, tmp_path, escaneos, catalogo):
        catalogo["Cámara de ionización"]["FC65-G"] = [(19, "1234", "2026-03-17", 0.048532178)]
        r = svc().leer(guardada(ventana, dialogos, tmp_path, escaneos))
        assert r["camara_factor"] == 0.048532178 and r["camara_equipo_id"] == 19

    @pytest.mark.parametrize("valor, esperado", [(0.048532178, 0.048532178), (1.0012345, 1.0012345), (464700.0, 464700.0), (5, 5.0), ("0.05394", 0.05394), ("4,85e-2", 0.0485), (None, None),
                                                 ("No Aplica", None), (float("nan"), None), (float("inf"), None), (True, None), (10 ** 400, None), (10 ** 5000, None), (object(), None)],
                             ids=["nueve_cifras", "ocho_cifras", "pozo", "entero", "texto", "texto_con_coma", "nada", "no_aplica", "nan", "infinito", "booleano", "no_cabe_en_un_real", "enorme", "objeto"])
    def test_numero_del_catalogo(self, valor, esperado):
        resultado = dibujo_mod().numero_del_catalogo(valor)
        assert resultado == esperado and (resultado is None or type(resultado) is float)


class TestLoQueLasPruebasDeLaRevisionNoVeian:
    """CD5-PROD-R1-03, 04 y 06 y CD5-PR-1, 3 y 4 (con CD5-PR-2 y 6 reforzadas en su sitio, arriba): la producción estaba bien y ninguna prueba atrapaba la mutación plausible."""

    def test_una_virgen_montada_que_no_es_valida_ni_se_usa_ni_impide_guardar(self, fabrica, dialogos, tmp_path, escaneos, monkeypatch):
        lienzo = gen.Lienzo(66.0, 66.0, 300.0, semilla=9)
        lienzo.pegar_pelicula(3.0, 3.0, 60.0, 60.0, (30.0, 30.0, 30.0), (1.0, 1.0, 1.0))          # una virgen negra: fuera del rango de una película sin irradiar
        mala = pel().piso_de_pelicula_virgen(lienzo.codificar(), _P(), "virgen_mala.tif", "2026-10-30")
        assert mala.estado != "ok"
        monkeypatch.setattr(pel(), "leer_referencia_virgen", lambda carpeta: mala)
        v = fabrica()
        assert "no es válida" in v.etiqueta_virgen.text() and v._virgen_utilizable() is None
        id_ = guardada(v, dialogos, tmp_path, escaneos)                               # con `return r` el servicio la rechaza y `guardada` no llega a «registro»
        assert svc().leer(id_)["virgen"] is None

    def test_abrir_con_los_ordenes_guardados_con_hueco_muestra_cada_pieza_en_su_fila(self, ventana, dialogos, tmp_path, escaneos):
        d = dibujo_mod()
        cargar_todas(ventana, dialogos, tmp_path, escaneos, cuales=set(range(2, 12)))      # sin la de 0 cGy: los órdenes guardados son 2 a 11 (la fila 1 no tiene imagen)
        llenar_el_encabezado(ventana)
        antes = [f[d.COLUMNA_DE_LA_CAPA["G"]] for f in celdas(ventana.tabla_piezas)[1:]]
        ventana.boton_guardar.click()
        assert ventana.estado == "registro", [c["texto"] for c in dialogos.llamadas]
        assert [p["orden"] for p in ventana._registro["piezas"]] == list(range(2, 12))
        despues = [f[d.COLUMNA_DE_LA_CAPA["G"]] for f in celdas(ventana.tabla_piezas)]
        assert despues == antes and len(despues) == 10 and all(re.fullmatch(r"\d\.\d{4} ± \d\.\d{4}", x) for x in despues)

    def test_la_pelicula_virgen_sin_dosis_medida_no_se_confirma(self, ventana, dialogos, tmp_path, escaneos):
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        escribir(ventana, 0, dibujo_mod().COLUMNA_MEDIDA, "")                         # la película virgen (0 cGy) sin dosis medida: lo natural (CD5-D12)
        llenar_el_encabezado(ventana)
        ventana.boton_guardar.click()
        assert ventana.estado == "registro" and dialogos.de("question") == []

    def test_volver_a_cargar_una_fila_no_cambia_que_la_curva_de_la_pantalla_sea_la_que_se_guarda(self, ventana, dialogos, tmp_path, escaneos):
        cargar_todas(ventana, dialogos, tmp_path, escaneos)
        cargar(ventana, dialogos, tmp_path, 4, "otra.tif", escaneos[7][2])            # la fila de 200 cGy, con otra imagen (la de 400 cGy)
        llenar_el_encabezado(ventana)
        en_pantalla = _json(ventana._curva.como_dict())
        ventana.boton_guardar.click()
        assert ventana.estado == "registro", [c["texto"] for c in dialogos.llamadas]
        assert svc().leer(ventana._registro["id"])["ajuste"] == en_pantalla

    def test_los_pares_del_grafico_son_los_del_ajuste_con_su_incertidumbre_y_la_curva_y_las_bandas_son_las_del_motor(self, ventana, dialogos, tmp_path, escaneos_saturantes):
        medidas = {o: d * 1.02 + 1.0 for o, (d, _n, _b) in escaneos_saturantes.items() if d > 0}          # la dosis medida NO es la nominal
        cargar_todas(ventana, dialogos, tmp_path, escaneos_saturantes, medidas=medidas)
        curva = ventana._curva
        pares, fuera = 0, 0
        for c in CAPAS:
            for grupo, en_el_rango in (("dentro", True), ("fuera", False)):
                esperadas = [p for p in curva.piezas if p.capas[c]["netod"] is not None and p.capas[c]["dosis_cgy"] is not None and bool(p.capas[c]["en_el_rango"]) == en_el_rango]
                contenedores = [k for k in ventana.eje_curva.containers if k.lines[0].get_gid() == f"piezas_{c}_{grupo}"]
                assert len(contenedores) == (1 if esperadas else 0), (c, grupo)
                if not esperadas:
                    continue
                linea, _topes, barras = contenedores[0].lines
                pares += len(esperadas)
                fuera += len(esperadas) if not en_el_rango else 0
                assert list(linea.get_xdata()) == pytest.approx([p.capas[c]["netod"] for p in esperadas]), (c, grupo)
                assert list(linea.get_ydata()) == pytest.approx([p.capas[c]["dosis_cgy"] for p in esperadas]), (c, grupo)
                assert [(s[1][0] - s[0][0]) / 2 for s in barras[0].get_segments()] == pytest.approx([p.capas[c]["u_netod"] for p in esperadas]), (c, grupo)
        assert pares >= 20 and fuera >= 1, "no vacuidad: pares dentro y fuera del rango útil"
        for c in CAPAS:
            tramos = [l for l in ventana.eje_curva.lines if (l.get_gid() or "").startswith(f"curva_{c}_")]
            assert tramos or curva.capas[c]["parametros"] is None
            for l in tramos:
                assert list(l.get_ydata()) == pytest.approx(list(curva.dosis(c, np.array(l.get_xdata()))))          # la curva de cada capa, con la ÚNICA definición del modelo (CD.9)
            for grupo, en_el_rango in (("dentro", True), ("fuera", False)):
                esperadas = [p for p in curva.piezas if p.capas[c]["residuo_pct"] is not None and p.capas[c]["dosis_cgy"] is not None and bool(p.capas[c]["en_el_rango"]) == en_el_rango]
                lineas = [l for l in ventana.eje_residuos.lines if l.get_gid() == f"residuos_{c}_{grupo}"]
                assert len(lineas) == (1 if esperadas else 0), (c, grupo)
                if esperadas:
                    assert list(lineas[0].get_xdata()) == pytest.approx([p.capas[c]["dosis_cgy"] for p in esperadas]) and list(lineas[0].get_ydata()) == pytest.approx([p.capas[c]["residuo_pct"] for p in esperadas])
        # las bandas de la tolerancia del motor (CD5-D9): ±`residuo_maximo_pct` desde `dosis_baja_cgy` hasta pasada la mayor dosis, y ±`residuo_maximo_bajas_pct` de 0 a `dosis_baja_cgy`
        P = curva.parametros
        baja, tolerancia, tolerancia_baja = P["dosis_baja_cgy"], P["residuo_maximo_pct"], P["residuo_maximo_bajas_pct"]
        mayor = max(p.capas[c]["dosis_cgy"] for p in curva.piezas for c in CAPAS if p.capas[c]["residuo_pct"] is not None and p.capas[c]["dosis_cgy"] is not None)
        segmentos = [(float(s[0][0]), float(s[0][1]), float(s[1][0])) for k in ventana.eje_residuos.collections for s in k.get_segments()]          # (dosis desde, residuo, dosis hasta)
        assert len(segmentos) == 4 and tolerancia != tolerancia_baja
        assert sorted(y for x0, y, x1 in segmentos if x0 == pytest.approx(baja)) == pytest.approx(sorted([tolerancia, -tolerancia])) and all(x1 >= mayor for x0, y, x1 in segmentos if x0 == pytest.approx(baja))
        assert sorted(y for x0, y, x1 in segmentos if x0 == pytest.approx(0.0)) == pytest.approx(sorted([tolerancia_baja, -tolerancia_baja])) and all(x1 == pytest.approx(baja) for x0, y, x1 in segmentos if x0 == pytest.approx(0.0))
