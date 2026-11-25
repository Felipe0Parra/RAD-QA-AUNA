"""Las etiquetas de «Resultados de aspectos mecánicos» (600 e iX) y las del Catphan no se enciman con su casilla, la unidad va entre corchetes y es la del PDF, y los códigos dicen CLA-F-RT-120 V.02 (anual) y CLA-F-RT-119 V.03 (mensual).

- Todo se deriva de `data/widgets.xlsx` tal como lo carga la app: pandas, `pose` con `ast.literal_eval` y una rejilla por `prueba`.
- La unidad de cada etiqueta y de su casilla es la de `services.unidades_qc.UNIDADES`, la tabla que imprime el PDF.
- La geometría se mide en los formularios reales, con la rejilla a su ancho mínimo y al doble.
- El código se lee en el encabezado de cada página del PDF que genera el botón «Reporte» de cada pantalla (el informe real, con el visor sustituido), no en lo que la pantalla le entrega.
"""
import ast
import gc
import os
import re
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pandas as pd
import pytest
from PyQt5.QtCore import QCoreApplication, QDate, QEvent, QRect
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

import data.ManejoDatos.conection as conection_mod
import models.PDF.Anual.reportes_anuales as anuales_mod
import models.PDF.Mensuales.reportes_mensuales as mensuales_mod
from data.ManejoDatos.conection import Conexion
from services.unidades_qc import UNIDADES
from ui.util_formato import codigo_de_formato

RAIZ = Path(__file__).resolve().parent.parent
LIBRO = RAIZ / "data" / "widgets.xlsx"
ETIQUETAS = {"QLabel", "QLabel Soft", "QLabel no usable"}
SECCION = "aspectos mecanicos"
MENSUALES = ("preguntas_mensu_600", "preguntas_mensu_ix")
CAMPOS = ("puntero_telem_diff", "telem_rango", "telem_desp", "camilla_vert_rango", "camilla_vert_desp", "camilla_iso_desp",
          "reticulo_cent", "iso_mec", "camp_luz_desp", "bordes_coin", "laser_techo", "laser_lateral27", "laser_lateral9")
CODIGO_ANUAL = ("CLA-F-RT-120", "V.02")
CODIGO_MENSUAL = ("CLA-F-RT-119", "V.03")
CODIGOS = {"encabezado_anual_600": CODIGO_ANUAL, "encabezado_anual_ix": CODIGO_ANUAL, "encabezado_anual_Halcyon": CODIGO_ANUAL,
           "encabezado_mensu_600": CODIGO_MENSUAL, "encabezado_mensu_IX": CODIGO_MENSUAL, "encabezado_mensu_Halcyon": CODIGO_MENSUAL}
FECHA_MENSUAL, FECHA_ANUAL = "15/03/2026", "03/2026"
PDF_DE_LA_PANTALLA = [("mensual_600", CODIGO_MENSUAL, "Mensual"), ("mensual_ix", CODIGO_MENSUAL, "Mensual"), ("mensual_halcyon", CODIGO_MENSUAL, "Mensual"),
                      ("anual_600", CODIGO_ANUAL, "Anual"), ("anual_ix", CODIGO_ANUAL, "Anual"), ("anual_halcyon", CODIGO_ANUAL, "Anual")]
# Lista revisada: el Halcyon no muestra su sección de aspectos mecánicos (ninguna caja la agrega), así que su hoja no se toca.
CRUCES_ACEPTADOS = {"preguntas_mensu_Halcyon": {(f"{'' if c in ('puntero_telem_diff', 'camp_luz_desp') else 'lbl_'}{c}_lbl",
                                                f"{'' if c in ('puntero_telem_diff', 'camp_luz_desp') else 'lbl_'}{c}") for c in CAMPOS}}
TAC_PRUEBAS = ("esp", "tp", "rc", "re", "ct", "uni")
TAC_CORTES = (("label_espesor", "ln_espesor"), ("label_contraste", "ln_contrast_res"),
              ("label_esp", "ln_resolucion_esp"), ("label_uniformidad", "ln_uni"))


def hojas(ruta=LIBRO):
    """{hoja: DataFrame} de las hojas con widgets, como DataFront.extrdatos (pose ya evaluada)."""
    x = pd.ExcelFile(ruta)
    salida = {}
    for h in x.sheet_names:
        df = pd.read_excel(x, sheet_name=h)
        if {"nombres", "widget_type", "pose"} <= set(df.columns):
            df = df[df["nombres"].notna()].copy()
            df["pose"] = df["pose"].apply(lambda v: ast.literal_eval(v) if isinstance(v, str) else v)
            salida[h] = df
    return salida


def celdas(pose):
    if not isinstance(pose, tuple) or len(pose) != 4:
        return set()
    r, c, rs, cs = pose
    return {(a, b) for a in range(r, r + rs) for b in range(c, c + cs)}


def cruces(df):
    """{(etiqueta, casilla)} que comparten una celda de la misma rejilla (misma `prueba`)."""
    filas = list(df.itertuples(index=False))
    salida = set()
    for a in filas:
        if a.widget_type not in ETIQUETAS:
            continue
        for b in filas:
            if b.widget_type not in ETIQUETAS and str(b.prueba) == str(a.prueba) and celdas(a.pose) & celdas(b.pose):
                salida.add((a.nombres, b.nombres))
    return salida


def nombres_del_campo(campo):
    casilla = campo if campo in ("puntero_telem_diff", "camp_luz_desp") else f"lbl_{campo}"
    return f"{casilla}_lbl", casilla


def texto(df, nombre):
    filas = df[df["nombres"] == nombre]
    assert len(filas) == 1, f"'{nombre}' aparece {len(filas)} veces"
    return str(filas.iloc[0]["descripcion"])


@pytest.fixture(scope="module")
def libro():
    return hojas()


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd(app, monkeypatch, tmp_path):
    """Una base temporal con el esquema de la app; Trampa 2: ningún modal se abre."""
    for nombre in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, nombre, staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QDialog, "exec_", lambda self: 0)
    ruta = str(tmp_path / "aj2.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    previa = Conexion._instance
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute("INSERT INTO users (fullname) VALUES ('Fisico Real')")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = previa


def cerrar(widget):
    """Trampa 9: cierra la página y vacía la cola de borrado."""
    widget.hide()
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


class _Usuario:
    _nombre = "Fisico Real"


def construir(clave):
    from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaAnualHalcyon
    from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX
    from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
    from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc
    from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
    from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
    from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
    return {"mensual_600": lambda: PruebaMensual600(user_id=None, equipo_f="Clinac 600"),
            "mensual_ix": lambda: PruebaMensualIX(user_id=None),
            "mensual_halcyon": lambda: PruebaMensualHc(user_id=None),
            "anual_600": lambda: PruebaAnual600(user_id=_Usuario(), equipo_f="Clinac 600"),
            "anual_ix": lambda: PruebaAnualIX(user_id=_Usuario()),
            "anual_halcyon": lambda: PruebaAnualHalcyon(user_id=_Usuario()),
            "tomografo": lambda: PruebaMensualTAC(user_id=None)}[clave]()


INICIAR = {"mensual_600": ["encabezado_mensu_600", "Control mensual", "Iniciar control mensual", "Clinac 600", "preguntas_mensu_600"],
           "mensual_ix": ["encabezado_mensu_IX", "Control mensual", "Iniciar control mensual", "Clinac ix", "preguntas_mensu_ix"],
           "tomografo": ["encabezado_mensu_TAC", "Control mensual", "Iniciar control mensual", "Tomógrafo", "preguntas_mensu_TAC"]}


def iniciado(clave):
    obj = construir(clave)
    obj.fisico1.addItem("Fisico Real", 1)
    obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
    obj.user_id_f1 = "Fisico Real"
    obj.user_id_f2 = None
    obj._iniciar_moviendo_tabla(INICIAR[clave])
    return obj


def abrir_qt(ruta):
    """La conexión de QtSql que leen los informes, apuntada a la base temporal."""
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.removeDatabase("qt_sql_default_connection")
    db = QSqlDatabase.addDatabase("QSQLITE")
    db.setDatabaseName(ruta)
    db.open()
    return db


def lineas_del_pdf_de(obj, ruta, monkeypatch, tipo):
    """Líneas de cada página del PDF del botón «Reporte» de `obj`: el informe real de un control vacío sembrado en `ruta`, con el visor sustituido y los avisos de error vigilados."""
    pdfs, errores = [], []

    class Visor:
        def __init__(self, pdf_data=None, **_):
            pdfs.append(bytes(pdf_data))

        def show(self):
            pass

    monkeypatch.setattr(mensuales_mod, "PdfViewer", Visor)
    monkeypatch.setattr(anuales_mod, "PdfViewer", Visor)
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: errores.append(a[1:3])))
    fecha = FECHA_MENSUAL if tipo == "Mensual" else FECHA_ANUAL
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO controles (equipo, control, fecha, user_id) VALUES (?, ?, ?, 'Fisico Real')", (obj.equipo_f, tipo, fecha))
    con.commit()
    con.close()
    if tipo == "Mensual":
        obj.fecha_control = fecha
    else:
        obj.date_box.setDate(QDate(2026, 3, 1))
    obj.opeenDatabase = lambda: abrir_qt(ruta)
    try:
        obj.generar_reporte_pdf()
    finally:
        if QSqlDatabase.contains("qt_sql_default_connection"):
            QSqlDatabase.removeDatabase("qt_sql_default_connection")
    assert (errores, len(pdfs)) == ([], 1), f"el informe falló o no salió una sola vez: avisos {errores}, PDF generados {len(pdfs)}"
    doc = fitz.open(stream=pdfs[0], filetype="pdf")
    try:
        return [p.get_text().splitlines() for p in doc]
    finally:
        doc.close()


def encimadas(obj, pares):
    """Pares cuya etiqueta termina a la derecha del comienzo de su casilla, con la rejilla a su ancho mínimo y al doble."""
    rejilla = getattr(obj, pares[0][0]).parentWidget().layout()
    minimo = rejilla.minimumSize()
    malos = []
    for ancho in (minimo.width(), 2 * minimo.width()):
        rejilla.setGeometry(QRect(0, 0, ancho, max(minimo.height(), 10)))
        for etiqueta, casilla in pares:
            a, b = getattr(obj, etiqueta), getattr(obj, casilla)
            assert a.parentWidget() is b.parentWidget(), (etiqueta, casilla)
            if a.geometry().right() >= b.geometry().left():
                malos.append(f"{a.text()!r} (borde derecho {a.geometry().right()} [px]) sobre {casilla} (borde izquierdo {b.geometry().left()} [px]) a {ancho} [px]")
    return malos


# ---------------------------------------------------------------------------
# (a) Ninguna etiqueta comparte celda con una casilla (salvo la lista revisada).
# ---------------------------------------------------------------------------

class TestCadaEtiquetaEnSuCelda:
    @pytest.mark.parametrize("hoja", MENSUALES + ("preguntas_mensu_TAC",))
    def test_la_hoja_no_tiene_cruces(self, libro, hoja):
        assert cruces(libro[hoja]) == set()

    def test_solo_el_halcyon_conserva_sus_cruces_revisados(self, libro):
        hallados = {h: c for h, df in libro.items() if (c := cruces(df))}
        assert hallados == CRUCES_ACEPTADOS

    @pytest.mark.parametrize("hoja", MENSUALES)
    def test_las_13_etiquetas_van_en_una_columna(self, libro, hoja):
        df = libro[hoja]
        poses = {nombres_del_campo(c)[0]: df[df["nombres"] == nombres_del_campo(c)[0]].iloc[0]["pose"] for c in CAMPOS}
        assert {n: p[1:] for n, p in poses.items()} == {n: (0, 1, 1) for n in poses}

    def test_las_25_etiquetas_del_catphan_van_en_una_columna(self, libro):
        df = libro["preguntas_mensu_TAC"]
        nombres = [f"{p}_lbl_{s}" for s in TAC_PRUEBAS + ("lin",) for p in ("kv", "ma", "ec")] + [e for e, _ in TAC_CORTES]
        assert len(nombres) == 25
        poses = {n: df[df["nombres"] == n].iloc[0]["pose"] for n in nombres}
        assert {n: p[1:] for n, p in poses.items()} == {n: (0, 1, 1) for n in nombres}

    def test_el_detector_ve_un_cruce_sintetico(self):
        df = pd.DataFrame([{"nombres": "e", "widget_type": "QLabel Soft", "pose": (1, 0, 1, 2), "prueba": "x"},
                           {"nombres": "c", "widget_type": "QLineEdit", "pose": (1, 1, 1, 2), "prueba": "x"},
                           {"nombres": "d", "widget_type": "QLineEdit", "pose": (1, 1, 1, 2), "prueba": "otra"}])
        assert cruces(df) == {("e", "c")}


# ---------------------------------------------------------------------------
# (b) La unidad de cada widget de la sección es la del PDF, entre corchetes.
# ---------------------------------------------------------------------------

class TestLaUnidadEsLaDelPdf:
    @pytest.mark.parametrize("hoja", MENSUALES)
    @pytest.mark.parametrize("campo", CAMPOS)
    def test_etiqueta_y_casilla_dicen_la_unidad_del_pdf(self, libro, hoja, campo):
        for nombre in nombres_del_campo(campo):
            t = texto(libro[hoja], nombre)
            assert re.findall(r"\[([^\[\]]+)\]", t) == [UNIDADES[campo]], f"{nombre}: {t!r}"
            assert "(" not in t and ")" not in t, f"{nombre}: unidad entre paréntesis en {t!r}"

    @pytest.mark.parametrize("hoja", MENSUALES)
    def test_la_seccion_tiene_exactamente_esas_13_etiquetas_y_13_casillas(self, libro, hoja):
        df = libro[hoja][libro[hoja]["prueba"] == SECCION]
        etiquetas = set(df[df["widget_type"] == "QLabel Soft"]["nombres"])
        casillas = set(df[df["widget_type"] == "QLineEdit"]["nombres"]) - {"observaciones"}
        assert etiquetas == {nombres_del_campo(c)[0] for c in CAMPOS}
        assert casillas == {nombres_del_campo(c)[1] for c in CAMPOS}

    def test_los_dos_rangos_dicen_centimetros(self, libro):
        for hoja in MENSUALES:
            for campo in ("telem_rango", "camilla_vert_rango"):
                assert [texto(libro[hoja], n) for n in nombres_del_campo(campo)] == ["· Rango [cm]", "Rango [cm]"]


# ---------------------------------------------------------------------------
# (c) Los códigos de formato, en el Excel, en la pantalla y en lo que recibe el PDF.
# ---------------------------------------------------------------------------

class TestLosCodigosDeFormato:
    def test_censo_de_los_seis_encabezados(self, libro):
        hallados = {h: tuple(dict(zip(libro[h]["nombres"], libro[h]["descripcion"]))[k] for k in ("code_1", "code_2")) for h in CODIGOS}
        assert hallados == CODIGOS

    def test_ningun_encabezado_de_acelerador_conserva_el_prefijo_viejo(self, libro):
        viejos = {h: c for h, df in libro.items() for c in df[df["nombres"] == "code_1"]["descripcion"] if str(c) in ("IDC-F-RT-119", "IDC-F-RT-120")}
        assert viejos == {}

    @pytest.mark.parametrize("clave,esperado,tipo", PDF_DE_LA_PANTALLA)
    def test_la_pantalla_y_su_pdf_dicen_el_codigo(self, bd, monkeypatch, clave, esperado, tipo):
        codigo = " ".join(esperado)
        encabezado = f"Control de calidad Control {tipo} {codigo}"
        obj = construir(clave)
        try:
            assert codigo_de_formato(obj) == codigo
            paginas = lineas_del_pdf_de(obj, bd, monkeypatch, tipo)
            assert paginas and all(encabezado in lineas for lineas in paginas), \
                f"se esperaba «{encabezado}» en cada página; hay {[[l for l in lineas if l.startswith('Control de calidad')] for lineas in paginas]}"
        finally:
            cerrar(obj)


# ---------------------------------------------------------------------------
# (d) Geometría en los formularios reales.
# ---------------------------------------------------------------------------

class TestNingunaEtiquetaQuedaBajoSuCasilla:
    @pytest.mark.parametrize("clave", ["mensual_600", "mensual_ix"])
    def test_aspectos_mecanicos(self, bd, clave):
        obj = iniciado(clave)
        try:
            assert encimadas(obj, [nombres_del_campo(c) for c in CAMPOS]) == []
        finally:
            cerrar(obj)

    def test_paginas_del_catphan(self, bd):
        obj = iniciado("tomografo")
        try:
            malos = []
            for s in TAC_PRUEBAS:
                malos += encimadas(obj, [(f"{p}_lbl_{s}", f"{p}_val_{s}") for p in ("kv", "ma", "ec")])
            malos += encimadas(obj, list(TAC_CORTES))
            assert malos == []
        finally:
            cerrar(obj)
