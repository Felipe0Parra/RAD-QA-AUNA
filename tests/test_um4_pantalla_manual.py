"""UM.4 (PLAN_CALCULADORA_UM_05-11.md, DC14, DC16): la pestaña «Calculadora UM», con la parte manual.

Lo que fija:
  - la CAPA PURA de `ui/paginasGuia/calculadora_um.py` sin crear widgets: la lectura de lo escrito (toda la clase de entradas raras, en todos los campos), el mapeo a `um_motor.Entrada`, los
    umbrales, el estado con el error SIN redondear y sus fronteras, el desglose y los textos;
  - la PANTALLA por el camino del físico (`QTest`): con las tablas reales del 600C cargadas por el servicio de UM.3 en una base TEMPORAL, los números de `logs/h_datos_reales.txt` y los de los
    ejemplos de la TG-71; cada factor del desglose es el del motor; sin tablas, fuera de tabla, fuera del campo o un valor imposible dan el motivo de `NoCalculable` y ningún número; los avisos,
    todos y en orden; un cambio de lo escrito, del equipo o de la energía borra el resultado; los umbrales cambian el estado y no las UM; Info no modal con sus temas; la ecuación dibujada sin
    `pyplot`; la pestaña al final de la ventana principal y los seis módulos en `build_exe.py`.
  - Lo que agregó la corrección de la revisión (10-11, ronda 1): el error se escribe con las cifras que piden los umbrales ESCRITOS; con cuña la orientación se elige (nunca se supone) y la elegida
    es la que llega al motor; un fallo pasajero de la base al abrir no se dice como un cambio de las tablas y el motivo de volver a leer el haz dice lo que pasó; el aviso de «sin tablas» dice lo
    mismo que la ayuda del botón «Cargar tablas» (que la carga llega después y quién la hace) y no manda a un botón que no responde.
Trampa 2: todo cuadro de diálogo se parcha y un modal hace caer la prueba (bajo `offscreen` colgaría la suite). Trampa 9: cada pantalla se cierra con la receta completa. Nunca una base de
BasesDeDatos/."""
import ast
import dataclasses
import gc
import os
import re
import shutil
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ui.paginasGuia.calculadora_um as pantalla      # primero: sin UM.4 la colección cae porque el módulo de la pantalla no existe (el rojo)
from PyQt5 import sip
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QDialog, QFileDialog, QLabel, QLineEdit, QListWidgetItem, QMessageBox, QSizePolicy,
                             QWidget)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services import um_datos_haz
from services import um_lector_eclipse as lector
from services import um_motor as motor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "tests", "datos_um", "600C")
EQUIPO, ENERGIA = "Clinac 600", "6 MV"
SIMBOLOS = re.compile("[✓✔✕✖✗✘⚠❌❎✅☑☒×✕]")   # DA-18 (× solo entre dos lados: se mira aparte)
ENTRE_PARENTESIS = re.compile(r"\s\((cm|mm|cGy|Gy|UM|MU|%|cGy/UM|grados)\)")                                       # NAV-D1
# Lo que escribe alguien que se equivoca, en CUALQUIER campo: nada de esto es un número para la calculadora.
RAROS = ("abc", "10cm", "10 cm", "1 0", "1e3", "1E-2", "inf", "-inf", "Infinity", "nan", "NaN", "1e999", "1,000.5", "1.000,5", "1_000", "１０", "٣", "0x10", "--1",
         "+-1", ".", ",", "1..2", "1,,2", "10%", "∞", "1/2", "2*3", "None", "True")
DEMASIADAS_CIFRAS = "9" * 400


# ================================================================================================================================== bases, pantallas y ayudas

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def dialogos(monkeypatch):
    """Trampa 2: ningún camino de la pantalla abre un cuadro modal. Si alguno lo intentara, la prueba cae aquí en lugar de colgar la suite."""
    def prohibido(*a, **k):
        raise AssertionError("la pantalla abrió un cuadro modal")
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(prohibido))
    for tipo in ("getOpenFileName", "getOpenFileNames", "getSaveFileName", "getExistingDirectory"):
        monkeypatch.setattr(QFileDialog, tipo, staticmethod(prohibido))
    monkeypatch.setattr(QDialog, "exec_", prohibido)
    monkeypatch.setattr(QDialog, "exec", prohibido)


@pytest.fixture(scope="module")
def originales():
    return [(nombre, open(os.path.join(DATOS, nombre), "rb").read()) for nombre in sorted(os.listdir(DATOS))]


def _abrir_con_la_app(ruta):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
        finally:
            Conexion._instance = previo


def _sql(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        filas = con.execute(sql, parametros).fetchall()
        con.commit()
        return filas
    finally:
        con.close()


@pytest.fixture(scope="module")
def plantilla_vacia(tmp_path_factory):
    ruta = str(tmp_path_factory.mktemp("um4") / "vacia.db")
    _abrir_con_la_app(ruta)
    _sql(ruta, "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) VALUES ('jefa', 'x', 'Jefa de Física', 1, 901, 'Físico Médico', 'jefe')")
    return ruta


@pytest.fixture(scope="module")
def plantilla(plantilla_vacia, originales, tmp_path_factory):
    """Una base con las tablas reales del 600C, 6 MV, cargadas por el servicio de UM.3 (D'0 = 1 cGy/UM en dmax)."""
    ruta = str(tmp_path_factory.mktemp("um4") / "cargada.db")
    shutil.copy(plantilla_vacia, ruta)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = object.__new__(Conexion)
        try:
            ok, motivo, _ = um_datos_haz.guardar(equipo=EQUIPO, energia=ENERGIA, archivos=originales, d0_dmax=1.0, d0_tabla=None, d0_origen="Eclipse: 1 cGy/UM en dmax",
                                                 wf_escritos=None, curva_sc=None, sc_origen=None, observaciones=None, usuario="jefa")
        finally:
            Conexion._instance = previo
    assert ok, motivo
    return ruta


def _usar(ruta, monkeypatch, tmp_path):
    copia = str(tmp_path / os.path.basename(ruta))
    shutil.copy(ruta, copia)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: copia)
    monkeypatch.setattr(Conexion, "_instance", object.__new__(Conexion))
    return copia


@pytest.fixture
def bd(plantilla, monkeypatch, tmp_path):
    return _usar(plantilla, monkeypatch, tmp_path)


@pytest.fixture
def bd_vacia(plantilla_vacia, monkeypatch, tmp_path):
    return _usar(plantilla_vacia, monkeypatch, tmp_path)


def cerrar(w, con_close=True):
    """Trampa 9: la receta completa (sin bucle de eventos, `deleteLater` + `gc.collect()` no liberan la pantalla). La ventana principal se suelta sin `close()`: su cierre hace un
    respaldo de la base (E9), que no es de esta prueba."""
    if sip.isdeleted(w):
        return
    w.hide()
    if con_close:
        w.close()
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


@pytest.fixture
def fabrica(app):
    hechas = []

    def nueva():
        hechas.append(pantalla.CalculadoraUM("jefa"))
        return hechas[-1]
    yield nueva
    for w in hechas:
        cerrar(w)


@pytest.fixture
def p(bd, fabrica):
    return fabrica()


@pytest.fixture(scope="module")
def datos_reales(plantilla):
    """El haz armado por el servicio con lo guardado (UM.3 prueba que es idéntico al de los archivos directos)."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: plantilla)
        previo = Conexion._instance
        Conexion._instance = object.__new__(Conexion)
        try:
            return um_datos_haz.datos_del_haz(EQUIPO, ENERGIA)
        finally:
            Conexion._instance = previo


def escribir(p, valores, cuna=None, orientacion=None, por_teclado=True):
    """Llena el formulario como el físico: borra cada campo y teclea (los no nombrados quedan vacíos; TF, 1.000) y elige la cuña y su orientación."""
    for clave, linea in p.campos.items():
        texto = valores.get(clave, "1.000" if clave == "tf" else "")
        if por_teclado:
            linea.selectAll()
            QTest.keyClick(linea, Qt.Key_Delete)
            QTest.keyClicks(linea, texto)
        else:
            linea.setText(texto)
    p.combo_cuna.setCurrentIndex(p.combo_cuna.findData(cuna))
    if orientacion is not None:
        p.combo_orientacion.setCurrentIndex(p.combo_orientacion.findData(orientacion))


def calcular_con_enter(p, campo="prof"):
    QTest.keyClick(p.campos[campo], Qt.Key_Return)


def entrada(**valores):
    return motor.Entrada(**valores)


def sin_numero(p):
    """Lo que se ve cuando no hay número: ni UM, ni error, ni estado, ni desglose, ni la línea de los campos (ni su lugar), ni avisos (el título sin su cuenta)."""
    return (p.resultado is None and p.etiqueta_um.text() == pantalla.SIN_RESULTADO and p.etiqueta_d_um.text() == "" and p.etiqueta_error.text() == ""
            and p.etiqueta_estado.text() == "" and p.tabla_desglose.rowCount() == 0 and p.etiqueta_campos.text() == "" and not p.etiqueta_campos.isVisibleTo(p)
            and p.lista_avisos.count() == 0 and p.titulo_avisos.text() == "Avisos" and not p.boton_copiar.isEnabled())


def celdas(tabla):
    return [tuple(tabla.item(i, j).text() for j in range(tabla.columnCount())) for i in range(tabla.rowCount())]


def avisos_de(p):
    return [p.lista_avisos.item(i).text() for i in range(p.lista_avisos.count())]


def servicio_falso(monkeypatch, haces):
    """Sustituye las tres lecturas del servicio por un diccionario {(equipo, energía): (id, DatosHaz)} y cuenta cuántas veces se arma un haz."""
    llamadas = []
    monkeypatch.setattr(um_datos_haz, "energias_cargadas", lambda equipo: [e for (q, e) in haces if q == equipo])
    monkeypatch.setattr(um_datos_haz, "vigente", lambda equipo, energia: {"id": haces[(equipo, energia)][0]} if (equipo, energia) in haces else None)

    def datos_del_haz(equipo, energia):
        llamadas.append((equipo, energia))
        return haces[(equipo, energia)][1] if (equipo, energia) in haces else None
    monkeypatch.setattr(um_datos_haz, "datos_del_haz", datos_del_haz)
    return llamadas


# ================================================================================================================================== la capa pura: leer lo escrito

@pytest.mark.parametrize("texto, valor", [("10", 10.0), ("10.5", 10.5), ("10,5", 10.5), (" 7 ", 7.0), ("-3", -3.0), ("+3", 3.0), ("−2.5", -2.5), (".5", 0.5), (",5", 0.5),
                                          ("5.", 5.0), ("0", 0.0), ("0.000", 0.0), (" 1.25 ", 1.25), ("007", 7.0)])
def test_leer_numero_acepta_cifras_con_punto_o_coma_y_signo(texto, valor):
    assert pantalla.leer_numero(texto, pantalla.POR_CLAVE["dosis"]) == valor


@pytest.mark.parametrize("campo", pantalla.CAMPOS, ids=lambda c: c.clave)
@pytest.mark.parametrize("raro", RAROS + (DEMASIADAS_CIFRAS,))
def test_nada_raro_es_un_numero_en_ningun_campo(campo, raro):
    """La CLASE entera: todos los campos por todas las entradas raras. Cada una da un motivo que nombra el campo, en español y sin símbolos, y nunca un número; ni el formulario entero
    pasa a ser una `Entrada`."""
    with pytest.raises(motor.FaltaDato) as fallo:
        pantalla.leer_numero(raro, campo)
    motivo = str(fallo.value)
    assert campo.nombre in motivo or (campo.nombre[0].upper() + campo.nombre[1:]) in motivo
    assert not SIMBOLOS.search(motivo) and not ENTRE_PARENTESIS.search(motivo)
    assert ("demasiadas cifras" in motivo) if raro == DEMASIADAS_CIFRAS else ("sin unidades" in motivo)
    textos = {c.clave: "10" for c in pantalla.CAMPOS}
    textos[campo.clave] = raro
    with pytest.raises(motor.FaltaDato) as todo:
        pantalla.entrada_desde_textos(textos, None, None)
    assert str(todo.value) == motivo


@pytest.mark.parametrize("campo", pantalla.CAMPOS, ids=lambda c: c.clave)
@pytest.mark.parametrize("vacio", ["", "   ", "\t"])
def test_un_campo_vacio_falta_si_es_obligatorio_y_vale_su_omision_si_no(campo, vacio):
    if campo.obligatorio:
        with pytest.raises(motor.FaltaDato, match=re.escape(f"Falta escribir {campo.nombre}.")):
            pantalla.leer_numero(vacio, campo)
    else:
        assert pantalla.leer_numero(vacio, campo) is campo.omision if campo.omision is None else pantalla.leer_numero(vacio, campo) == campo.omision


def test_lo_que_vale_vacio_cada_campo():
    """Obligatorios: dosis, mandíbulas, SSD, profundidad y TF. El centro y el punto valen 0 vacíos (DC4: 0 si es simétrico, 0 en el isocentro); los demás opcionales no se usan."""
    assert {c.clave for c in pantalla.CAMPOS if c.obligatorio} == {"dosis", "x", "y", "ssd", "prof", "tf"}
    assert {c.clave: c.omision for c in pantalla.CAMPOS if not c.obligatorio} == {"centro_x": 0.0, "centro_y": 0.0, "x_ef": None, "y_ef": None, "prof_ef": None, "punto_x": 0.0,
                                                                              "punto_y": 0.0, "oar_manual": None, "wf_manual": None, "um_planeador": None}
    assert pantalla.POR_CLAVE["tf"].inicial == "1.000" and all(c.inicial == "" for c in pantalla.CAMPOS if c.clave != "tf")


# Lo que ve el físico, LITERAL (cada etiqueta, cómo lo nombra un motivo, si es obligatorio, lo que vale vacío, su texto inicial, su ayuda gris y su ayuda emergente): un cambio en un texto
# es un cambio de lo que ve el físico y tiene que pasar por esta tabla (el barrido por AST de la capa pura lo exige).
TABLA_DE_CAMPOS = [
    ("dosis", "Dosis del campo en el punto [cGy]", "la dosis del campo en el punto [cGy]", True, None, "", "", "La dosis que da este campo en el punto de cálculo, según el plan."),
    ("x", "Lado X de las mandíbulas [cm]", "el lado X de las mandíbulas [cm]", True, None, "", "", "En el isocentro. Con Eclipse, x1 + x2."),
    ("y", "Lado Y de las mandíbulas [cm]", "el lado Y de las mandíbulas [cm]", True, None, "", "", "En el isocentro. Con Eclipse, y1 + y2."),
    ("centro_x", "Centro del campo X [cm]", "el centro del campo X [cm]", False, 0.0, "", "opcional: 0",
     "Opcional. El centro del campo de las mandíbulas respecto al eje; vacío vale 0, un campo simétrico. Con Eclipse, (x2 − x1)/2."),
    ("centro_y", "Centro del campo Y [cm]", "el centro del campo Y [cm]", False, 0.0, "", "opcional: 0",
     "Opcional. El centro del campo de las mandíbulas respecto al eje; vacío vale 0, un campo simétrico. Con Eclipse, (y2 − y1)/2."),
    ("x_ef", "Lado X del campo equivalente [cm]", "el lado X del campo equivalente [cm]", False, None, "", "opcional",
     "Opcional. El campo que dejan las láminas o el bloque en el isocentro, como rectángulo o como su cuadrado equivalente; vacío, el de las mandíbulas."),
    ("y_ef", "Lado Y del campo equivalente [cm]", "el lado Y del campo equivalente [cm]", False, None, "", "opcional",
     "Opcional. El campo que dejan las láminas o el bloque en el isocentro, como rectángulo o como su cuadrado equivalente; vacío, el de las mandíbulas."),
    ("ssd", "SSD [cm]", "la SSD [cm]", True, None, "", "", "La distancia de la fuente a la superficie."),
    ("prof", "Profundidad [cm]", "la profundidad [cm]", True, None, "", "", "La profundidad física del punto de cálculo."),
    ("prof_ef", "Profundidad efectiva [cm]", "la profundidad efectiva [cm]", False, None, "", "opcional",
     "Opcional. Si el plan corrige por heterogeneidad; vacío, no se corrige. Con ella se mueve el campo de lectura del PDD y del factor de campo; el OAR y el factor de cuña siguen en la "
     "profundidad física."),
    ("punto_x", "Punto X desde el eje [cm]", "el punto X desde el eje [cm]", False, 0.0, "", "opcional: 0",
     "Opcional. La posición del punto de cálculo respecto al eje del haz, en el plano del isocentro (no a la profundidad del cálculo); vacío vale 0, el punto sobre el eje del haz."),
    ("punto_y", "Punto Y desde el eje [cm]", "el punto Y desde el eje [cm]", False, 0.0, "", "opcional: 0",
     "Opcional. La posición del punto de cálculo respecto al eje del haz, en el plano del isocentro (no a la profundidad del cálculo); vacío vale 0, el punto sobre el eje del haz."),
    ("oar_manual", "OAR", "el OAR", False, None, "", "opcional", "Opcional. Vacío, sale de los perfiles cargados (sobre el eje vale 1); escrito, manda lo escrito."),
    ("wf_manual", "Factor de cuña WF", "el factor de cuña WF", False, None, "", "opcional",
     "Opcional. Vacío, sale de las tablas de la cuña elegida; escrito, manda lo escrito, también sin cuña elegida (una cuña dinámica)."),
    ("tf", "Factor de bandeja TF", "el factor de bandeja TF", True, None, "1.000", "", "1.000 sin bandeja."),
    ("um_planeador", "UM de Eclipse [UM]", "las UM de Eclipse [UM]", False, None, "", "opcional", "Opcional. Con ellas se calculan el error y el estado; vacío, no se compara."),
]
TEXTOS_FIJOS = {"SIN_CUNA": "Sin cuña", "ELIJA_ORIENTACION": "Elija la orientación", "TITULO_DE_LA_INFO": "Calculadora UM: de dónde sale cada número", "SIN_RESULTADO": "Sin resultado",
                "SIN_UM_DE_ECLIPSE": "Sin UM de Eclipse: no hay error ni estado.",
                "ECUACION_TEXTO": "UM = D · 100 / [D'0 · Sc(rc) · Sp(rd0) · PDD_N(d, r, SSD) · WF · TF · OAR · ((SSD0 + d0)/(SSD + d0))²]",
                "ECUACION_MATHTEXT": (r"$UM = \dfrac{D \cdot 100}{D'_0 \cdot S_c(r_c) \cdot S_p(r_{d_0}) \cdot PDD_N(d, r, SSD) \cdot WF \cdot TF \cdot OAR \cdot "
                                      r"\left(\dfrac{SSD_0 + d_0}{SSD + d_0}\right)^2}$"),
                "LA_JSON_LLEGA_DESPUES": ("La parte automática, que calcula cada campo de un plan a partir de un JSON con la misma cuenta de la parte manual, llega en una próxima entrega "
                                          "de la calculadora."),
                "CARGAR_TABLAS_LLEGA_DESPUES": "La carga de tablas se habilita en la próxima entrega de la calculadora; la hacen el físico jefe o el administrador.",
                "EQUIPOS": ("Clinac 600", "Clinac iX")}


def test_la_tabla_de_campos_y_los_textos_fijos_son_los_que_ve_el_fisico():
    assert [(c.clave, c.etiqueta, c.nombre, c.obligatorio, c.omision, c.inicial, c.ayuda, c.explicacion) for c in pantalla.CAMPOS] == TABLA_DE_CAMPOS
    assert [(clave, etiqueta, nombre) for clave, etiqueta, nombre, _ in pantalla.UMBRALES] == [("dentro", "Dentro hasta [%]", "el umbral de Dentro [%]"),
                                                                                              ("fuera", "Revisar hasta [%]; más es Fuera", "el umbral de Revisar [%]")]
    for nombre, texto in TEXTOS_FIJOS.items():
        assert getattr(pantalla, nombre) == texto, nombre
    with pytest.raises(dataclasses.FrozenInstanceError):
        pantalla.CAMPOS[0].obligatorio = False      # la tabla no se cambia en marcha


def test_cada_etiqueta_de_la_pantalla_es_la_de_la_tabla(p):
    for clave, etiqueta, *_ in TABLA_DE_CAMPOS:
        assert p.etiquetas[clave].text() == etiqueta, clave
    assert (p.etiquetas["cuna"].text(), p.etiquetas["cuna_orientacion"].text()) == ("Cuña", "Orientación de la cuña")
    assert (p.etiquetas["dentro"].text(), p.etiquetas["fuera"].text()) == ("Dentro hasta [%]", "Revisar hasta [%]; más es Fuera")
    assert p.combo_cuna.itemText(0) == "Sin cuña" and p.combo_orientacion.itemText(0) == "Elija la orientación"
    assert [p.combo_orientacion.itemText(i) for i in range(1, p.combo_orientacion.count())] == list(motor.ORIENTACIONES)
    assert p.etiqueta_um.text() == "Sin resultado" and p.boton_calcular.text() == "Calcular" and p.boton_copiar.text() == "Copiar el desglose" and p.boton_info.text() == "Info"


BASE = {"dosis": "200", "x": "10", "y": "10", "ssd": "100", "prof": "10", "tf": "1.000"}


@pytest.mark.parametrize("campo", [c for c in pantalla.CAMPOS if not c.obligatorio and c.omision is None], ids=lambda c: c.clave)
def test_un_cero_escrito_en_un_opcional_no_cae_al_valor_por_omision(campo, datos_reales):
    """Un 0 escrito llega al motor como 0 (no como «vacío»), y el motor lo rechaza con su motivo: ninguno de estos opcionales puede valer 0. Con el campo vacío, en cambio, sí hay número."""
    textos = dict(BASE, **({"x_ef": "5", "y_ef": "5"} if campo.clave in ("x_ef", "y_ef") else {}))
    textos[campo.clave] = "0"
    e = pantalla.entrada_desde_textos(textos, None, None)
    assert getattr(e, campo.clave) == 0.0 and getattr(e, campo.clave) is not None
    with pytest.raises(motor.NoCalculable):
        motor.calcular(datos_reales, e)
    textos[campo.clave] = ""
    if campo.clave in ("x_ef", "y_ef"):
        textos["x_ef"] = textos["y_ef"] = ""
    assert motor.calcular(datos_reales, pantalla.entrada_desde_textos(textos, None, None)).um > 0


def test_cada_campo_llega_a_su_atributo_de_la_entrada():
    """Valores distintos en cada campo: un campo cruzado con otro (X con Y, centro con punto) se ve."""
    textos = {c.clave: f"{i + 1}.{i + 3}" for i, c in enumerate(pantalla.CAMPOS)}
    e = pantalla.entrada_desde_textos(textos, 15, "LEFT")
    for i, c in enumerate(pantalla.CAMPOS):
        assert getattr(e, c.clave) == float(f"{i + 1}.{i + 3}"), c.clave
    assert (e.cuna, e.cuna_orientacion) == (15, "LEFT")
    sin_cuna = pantalla.entrada_desde_textos(textos, None, "OUT")
    assert sin_cuna.cuna is None and sin_cuna.cuna_orientacion == motor.Entrada.__dataclass_fields__["cuna_orientacion"].default


def test_todos_los_motivos_de_lectura_juntos_y_en_el_orden_del_formulario():
    textos = {"dosis": "", "x": "diez", "y": "", "centro_x": "1cm", "ssd": "", "prof": "", "tf": ""}
    with pytest.raises(motor.FaltaDato) as fallo:
        pantalla.entrada_desde_textos(textos, 15, None)
    lineas = str(fallo.value).split("\n")
    assert lineas == ["Falta escribir la dosis del campo en el punto [cGy].",
                      "No se entiende el lado X de las mandíbulas [cm]: «diez». Escriba solo el número, con punto o coma decimal y sin unidades.",
                      "Falta escribir el lado Y de las mandíbulas [cm].",
                      "No se entiende el centro del campo X [cm]: «1cm». Escriba solo el número, con punto o coma decimal y sin unidades.",
                      "Falta escribir la SSD [cm].", "Falta escribir la profundidad [cm].", "Falta escribir el factor de bandeja TF.",
                      "Con cuña, elija su orientación: IN u OUT si el gradiente va a lo largo de Y; LEFT o RIGHT si va a lo largo de X."]


@pytest.mark.parametrize("orientacion", motor.ORIENTACIONES)
def test_con_cuna_la_orientacion_es_obligatoria_y_llega_tal_cual(orientacion):
    with pytest.raises(motor.FaltaDato, match="Con cuña, elija su orientación"):
        pantalla.entrada_desde_textos(BASE, 15, None)
    assert pantalla.entrada_desde_textos(BASE, 15, orientacion).cuna_orientacion == orientacion


# ================================================================================================================================== la capa pura: umbrales, estado y textos

@pytest.mark.parametrize("dentro, fuera, esperado", [("2", "3", (2.0, 3.0)), ("2,5", "4", (2.5, 4.0)), ("1", "1", (1.0, 1.0)), (" 0.5 ", "10", (0.5, 10.0))])
def test_umbrales_validos(dentro, fuera, esperado):
    assert pantalla.umbrales_desde_textos(dentro, fuera) == esperado


REGLA_DEL_MOTOR = "Las tolerancias deben ser números mayores que 0, la de dentro no mayor que la de fuera [%]: "


@pytest.mark.parametrize("dentro, fuera, motivo", [
    ("0", "3", REGLA_DEL_MOTOR + "0.0 y 3.0"), ("-1", "3", REGLA_DEL_MOTOR + "-1.0 y 3.0"),
    ("3", "2", REGLA_DEL_MOTOR + "3.0 y 2.0"), ("", "3", "Falta escribir el umbral de Dentro [%]."),
    ("2", "", "Falta escribir el umbral de Revisar [%]."), ("2", "3%", "No se entiende el umbral de Revisar [%]: «3%»"), ("nan", "3", "No se entiende el umbral de Dentro [%]: «nan»")])
def test_umbrales_que_no_sirven_dicen_por_que(dentro, fuera, motivo):
    """La pantalla lee los dos números; qué umbrales sirven lo decide el motor (la regla de `um_motor.estado_de`), con su motivo."""
    with pytest.raises(motor.FaltaDato) as fallo:
        pantalla.umbrales_desde_textos(dentro, fuera)
    assert str(fallo.value).startswith(motivo)
    if motivo.startswith(REGLA_DEL_MOTOR):
        with pytest.raises(motor.FaltaDato) as del_motor:
            motor.estado_de(0.0, float(dentro), float(fuera))
        assert str(fallo.value) == str(del_motor.value)


@pytest.mark.parametrize("error, texto, estado", [
    (0.0, "+0.00", "Dentro"), (1.0, "+1.00", "Dentro"), (2.0, "+2.00", "Dentro"), (-2.0, "-2.00", "Dentro"), (1.996, "+1.996", "Dentro"), (1.99999, "+1.99999", "Dentro"),
    (2.004, "+2.004", "Revisar"), (-2.004, "-2.004", "Revisar"), (2.0000001, "+2.0000001", "Revisar"), (2.5, "+2.50", "Revisar"), (3.0, "+3.00", "Revisar"),
    (-3.0, "-3.00", "Revisar"), (3.0004, "+3.0004", "Fuera"), (-3.0004, "-3.0004", "Fuera"), (2.996, "+2.996", "Revisar"), (3.5, "+3.50", "Fuera"), (-12.25, "-12.25", "Fuera")])
def test_el_estado_va_con_el_error_sin_redondear_y_el_texto_no_se_lee_igual_que_el_umbral(error, texto, estado):
    """Frontera de 2 y 3 [%]: el estado lo decide `um_motor.estado_de` con el error SIN redondear; el texto lleva dos decimales y los que hagan falta para no leerse igual que un umbral
    que no es el suyo (con dos, 2.004 se leía «2.00» con estado Revisar)."""
    assert pantalla.texto_del_error(error, (2.0, 3.0)) == f"Error frente a Eclipse: {texto} [%]"
    assert pantalla.texto_del_estado(error, ("2", "3")) == f"Estado: {estado}"
    assert pantalla.texto_del_estado(error, ("2", "3")) == f"Estado: {motor.estado_de(error, 2.0, 3.0)}"


def test_el_estado_con_otros_umbrales_y_con_umbrales_que_no_sirven():
    assert pantalla.texto_del_estado(2.5, ("3", "4")) == "Estado: Dentro"
    assert pantalla.texto_del_estado(2.5, ("1", "2")) == "Estado: Fuera"
    assert pantalla.texto_del_estado(2.5, ("3", "2")) == "Estado sin evaluar: " + REGLA_DEL_MOTOR + "3.0 y 2.0"
    assert pantalla.texto_del_error(2.004, ()) == "Error frente a Eclipse: +2.00 [%]"
    assert pantalla.texto_del_error(2.5004, (2.5, 4.0)) == "Error frente a Eclipse: +2.5004 [%]"


def test_los_umbrales_iniciales_son_los_del_motor():
    assert [(clave, valor) for clave, _, _, valor in pantalla.UMBRALES] == [("dentro", motor.TOLERANCIA_DENTRO_PCT), ("fuera", motor.TOLERANCIA_FUERA_PCT)]


def test_el_desglose_y_los_campos_son_los_del_motor_sin_redondear_antes(datos_reales):
    r = motor.calcular(datos_reales, entrada(dosis=200.0, x=15.0, y=15.0, x_ef=10.0, y_ef=10.0, ssd=90.0, prof=10.0, um_planeador=245.0))
    assert pantalla.filas_del_desglose(r) == [(f.simbolo, f"{f.valor:.4f}", f.origen, f.detalle) for f in r.factores]
    assert [f[0] for f in pantalla.filas_del_desglose(r)] == ["D", "D'0", "OF", "Sc(rc)/Sc(lectura)", "PDD_N", "WF", "TF", "OAR", "Inverso del cuadrado",
                                                              "Corrección por profundidad efectiva"]
    assert pantalla.filas_de_los_campos(r) == [("rc", f"{r.campos['rc']:.2f} [cm]", "Campo de las mandíbulas en el isocentro"),
                                               ("r", f"{r.campos['r']:.2f} [cm]", "Campo efectivo en la superficie"),
                                               ("rd0", f"{r.campos['rd0']:.2f} [cm]", "Campo efectivo a la profundidad d0 de la tabla"),
                                               ("OF en las mandíbulas", f"{r.lectura_alterna_of:.4f}",
                                                "Lectura alterna: la tabla leída directamente en las mandíbulas del isocentro, sin corregir")]
    assert pantalla.texto_de_los_campos(r) == (f"Campos: rc {r.campos['rc']:.2f} [cm]; r {r.campos['r']:.2f} [cm]; rd0 {r.campos['rd0']:.2f} [cm]. "
                                               f"OF en las mandíbulas: {r.lectura_alterna_of:.4f}")
    assert (r.campos["rc"], r.campos["r"], r.campos["rd0"]) == (15.0, 9.0, pytest.approx(9.5))
    assert pantalla.texto_de_las_um(r) == f"UM calculadas: {r.um:.1f} [UM]" and pantalla.texto_de_d_um(r) == f"D/UM: {r.d_um:.4f} [cGy/UM]"


def test_el_texto_para_copiar_trae_todo(datos_reales):
    r = motor.calcular(datos_reales, entrada(dosis=200.0, x=4.0, y=3.0, x_ef=3.0, y_ef=2.6, ssd=125.0, prof=1.0))
    texto = pantalla.texto_para_copiar(r)
    lineas = texto.split("\n")
    assert lineas[:4] == [pantalla.texto_de_las_um(r), pantalla.texto_de_d_um(r), "", "Factor\tValor\tOrigen\tDetalle"]
    assert lineas[4:14] == ["\t".join(f) for f in pantalla.filas_del_desglose(r)]
    assert lineas[14:20] == ["", "Campo\tValor\tQué es"] + ["\t".join(f) for f in pantalla.filas_de_los_campos(r)]
    assert lineas[20:] == ["", "Avisos"] + list(r.avisos) and len(r.avisos) >= 5


def test_sin_tablas_dice_que_falta_quien_carga_y_que_la_carga_llega_despues():
    """UM4-D1: el aviso dice lo mismo que la ayuda del botón «Cargar tablas» (que la carga se habilita en la próxima entrega y quién la hace) y no manda al botón, que en UM.4 no responde."""
    for equipo in pantalla.EQUIPOS:
        texto = pantalla.texto_sin_tablas(equipo)
        assert f"No hay tablas cargadas del {equipo}: sin ellas no se puede calcular." in texto
        assert pantalla.CARGAR_TABLAS_LLEGA_DESPUES in texto and "próxima entrega" in texto
        assert "el físico jefe o el administrador" in texto and "una vez por energía" in texto     # UM.3: guardar exige es_fisico_jefe; los demás ven y calculan
        assert "«Cargar tablas»" not in texto


# Por qué se detuvo `calcular` al volver a leer el haz (UM4-D9): lo que dice la pantalla es lo que pasó con esa lectura, nunca otra cosa.
TABLAS_CAMBIARON = "Las tablas de este haz cambiaron desde que se eligió la energía: se volvieron a leer. Revise la cuña y pulse Calcular otra vez."
TABLAS_NO_LEIDAS = "Las tablas de este haz no se habían podido leer al elegir la energía: ya se leyeron. Revise la cuña y pulse Calcular otra vez."


@pytest.mark.parametrize("antes, ahora, esperado", [(11, 12, TABLAS_CAMBIARON), (12, 11, TABLAS_CAMBIARON), (None, 5, TABLAS_NO_LEIDAS), (11, None, "el aviso"), (None, None, "el aviso")],
                         ids=["otro_conjunto", "otro_conjunto_anterior", "nunca_se_habia_leido", "la_relectura_falla", "ninguna_de_las_dos_se_pudo"])
def test_el_motivo_de_volver_a_leer_el_haz_dice_lo_que_paso(antes, ahora, esperado):
    """Otro conjunto vigente: «cambiaron». Nunca se había leído (la lectura de elegir la energía falló) y ahora sí: «no se habían podido leer». La relectura también falla: ese fallo, el mismo del aviso."""
    assert pantalla.texto_de_la_relectura(antes, ahora, "el aviso") == esperado


# ================================================================================================================================== la pantalla: los números son los del motor

# logs/UM2/h_datos_reales_UM2.txt (UM.2 comiteada, b1f14b3; D = 200 cGy, D'0 = 1 cGy/UM en dmax): (formulario, cuña, UM del log).
CASOS_REALES = [
    ({"x": "10", "y": "10", "ssd": "100", "prof": "10"}, None, "302.1"),
    ({"x": "10", "y": "10", "ssd": "90", "prof": "10"}, None, "252.8"),
    ({"x": "10", "y": "15", "ssd": "92", "prof": "8"}, None, "228.4"),
    ({"x": "15", "y": "15", "x_ef": "10", "y_ef": "10", "ssd": "90", "prof": "10"}, None, "250.5"),
    ({"x": "20", "y": "20", "ssd": "90", "prof": "10", "punto_x": "5"}, None, "224.9"),
    ({"x": "20", "y": "20", "ssd": "90", "prof": "10", "punto_x": "8"}, None, "223.3"),
    ({"x": "10", "y": "10", "ssd": "90", "prof": "15", "prof_ef": "8"}, None, "256.3"),
    ({"x": "10", "y": "10", "ssd": "90", "prof": "10"}, 15, "326.8"),
    ({"x": "15", "y": "15", "ssd": "90", "prof": "10"}, 15, "306.7"),
    ({"x": "5", "y": "5", "ssd": "90", "prof": "10"}, None, "279.6"),
]


def _entrada_de(valores, cuna):
    return pantalla.entrada_desde_textos(dict({"dosis": "200", "tf": "1.000"}, **valores), cuna, "IN" if cuna else None)


@pytest.mark.parametrize("valores, cuna, um_del_log", CASOS_REALES, ids=[c[2] for c in CASOS_REALES])
def test_llenar_el_formulario_por_teclado_da_los_numeros_de_los_datos_reales(p, datos_reales, valores, cuna, um_del_log):
    escribir(p, dict(valores, dosis="200"), cuna, "IN" if cuna else None)
    assert sin_numero(p)
    calcular_con_enter(p)
    directo = motor.calcular(datos_reales, _entrada_de(valores, cuna))
    assert p.etiqueta_um.text() == f"UM calculadas: {um_del_log} [UM]" == pantalla.texto_de_las_um(directo)
    assert p.etiqueta_d_um.text() == pantalla.texto_de_d_um(directo)
    assert celdas(p.tabla_desglose) == pantalla.filas_del_desglose(directo)
    assert p.etiqueta_campos.text() == pantalla.texto_de_los_campos(directo)
    assert avisos_de(p) == list(directo.avisos) and p.titulo_avisos.text() == f"Avisos ({len(directo.avisos)})"
    assert p.resultado == directo
    assert p.etiqueta_error.text() == pantalla.SIN_UM_DE_ECLIPSE and p.etiqueta_estado.text() == "" and not p.etiqueta_motivo.isVisibleTo(p)
    assert p.etiqueta_campos.isVisibleTo(p)       # la línea «Campos» (rc, r, rd0 y la lectura alterna del OF) se VE con el resultado: el texto solo no basta


def test_el_primero_se_comprueba_a_mano(p):
    """§8 de la puerta: 200/0.662 (D'0 0.860 a 5 cm por el PDD de 10 a 5 cm del 10 × 10)."""
    escribir(p, {"dosis": "200", "x": "10", "y": "10", "ssd": "100", "prof": "10"})
    calcular_con_enter(p)
    assert p.resultado.um == pytest.approx(200 / 0.662, rel=1e-3)
    assert dict((f[0], f[1]) for f in celdas(p.tabla_desglose))["D'0"] == "0.8600"


# El haz de los ejemplos de la TG-71 (como en tests/test_um2_motor.py::haz_tg71): tabla IV y las filas de la tabla II que usan; SSD0 = 90, d0 = 10, D'0 = 0.8.
def _haz_tg71():
    import math

    import numpy as np
    lados = np.array([4.0, 5, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40])
    scp = np.array([.866, .895, .922, .964, 1.0, 1.028, 1.051, 1.070, 1.102, 1.127, 1.149, 1.167, 1.194])
    m = np.array([[np.interp(math.log(motor.equivalente(x, y)), np.log(lados), scp) for x in lados] for y in lados])
    pdd = motor.FamiliaPDD(np.array([4.0, 5, 9, 10, 11, 12]), np.array([6.0, 9.5, 10.0]),
                           np.array([[127.7, 103.2, 100.0], [126.6, 102.7, 100.0], [123.8, 102.6, 100.0], [123.2, 102.5, 100.0], [122.7, 102.5, 100.0], [122.3, 102.6, 100.0]]))
    return motor.DatosHaz("TG-71", "6 MV", 90.0, 10.0, 0.8, pdd, motor.TablaFactores(lados, lados, m))


EJ2 = {"dosis": "90", "x": "18", "y": "12", "ssd": "90", "prof": "10", "x_ef": "14", "y_ef": "8", "wf_manual": "0.711"}
EJ3 = {"dosis": "45", "x": "5.5", "y": "7", "ssd": "90.5", "prof": "9.5", "x_ef": "4", "y_ef": "5"}
# Publicado por la TG-71 y lo que da el motor de UM.2 comiteada (logs/UM2/h_datos_reales_UM2.txt): los cuatro con láminas o bloque cambiaron en la segunda cifra decimal frente a la v1.
EJEMPLOS_TG71 = [({"dosis": "250", "x": "10", "y": "15", "ssd": "94", "prof": "6"}, 266.0, 266.08), (EJ2, 156.0, 155.65), (dict(EJ2, prof_ef="6"), 135.0, 135.28),
                 (dict(EJ3, wf_manual="0.845"), 73.0, 72.84), (dict(EJ3, wf_manual="0.892", oar_manual="1.005"), 69.0, 68.65)]


@pytest.mark.parametrize("valores, publicado, del_log", EJEMPLOS_TG71, ids=["ej1", "ej2", "ej2_def", "ej3", "ej3_oar"])
def test_los_ejemplos_de_la_tg71_por_la_pantalla(app, fabrica, monkeypatch, valores, publicado, del_log):
    haz = _haz_tg71()
    servicio_falso(monkeypatch, {(EQUIPO, ENERGIA): (7, haz)})
    p = fabrica()
    escribir(p, valores)
    calcular_con_enter(p)
    directo = motor.calcular(haz, pantalla.entrada_desde_textos(dict({"tf": "1.000"}, **valores), None, None))
    assert directo.um == pytest.approx(del_log, abs=0.005) and directo.um == pytest.approx(publicado, abs=0.5)
    assert p.etiqueta_um.text() == f"UM calculadas: {directo.um:.1f} [UM]"
    assert celdas(p.tabla_desglose) == pantalla.filas_del_desglose(directo) and avisos_de(p) == list(directo.avisos)


# ================================================================================================================================== la pantalla: lo que no da número

MOTIVOS = [
    ("fuera de tabla", {"x": "2.5", "y": "2.5", "ssd": "90", "prof": "10"}, None, None, motor.FueraDeTabla),
    ("profundidad fuera", {"x": "10", "y": "10", "ssd": "100", "prof": "35"}, None, None, motor.FueraDeTabla),
    ("punto fuera del campo", {"x": "10", "y": "10", "ssd": "90", "prof": "10", "punto_x": "6"}, None, None, motor.FueraDelCampo),
    ("efectivo mayor", {"x": "10", "y": "10", "ssd": "90", "prof": "10", "x_ef": "20", "y_ef": "20"}, None, None, motor.FueraDelCampo),
    ("cuña sin factor", {"x": "10", "y": "10", "ssd": "90", "prof": "10"}, 30, "IN", motor.FaltaDato),
    ("cuña fuera del eje", {"x": "10", "y": "10", "ssd": "90", "prof": "10", "punto_x": "2"}, 15, "IN", motor.FaltaDato),
    ("OAR imposible", {"x": "10", "y": "10", "ssd": "90", "prof": "10", "oar_manual": "1.5"}, None, None, motor.FaltaDato),
    ("OAR que pide escribirse", {"x": "40", "y": "40", "ssd": "100", "prof": "25", "punto_x": "17"}, None, None, motor.FueraDeTabla),
    ("WF imposible", {"x": "10", "y": "10", "ssd": "90", "prof": "10", "wf_manual": "77"}, None, None, motor.FaltaDato),
    ("TF imposible", {"x": "10", "y": "10", "ssd": "90", "prof": "10", "tf": "95"}, None, None, motor.FaltaDato),
    ("SSD imposible", {"x": "10", "y": "10", "ssd": "50", "prof": "10"}, None, None, motor.FaltaDato),
    ("dosis cero", {"dosis": "0", "x": "10", "y": "10", "ssd": "90", "prof": "10"}, None, None, motor.FaltaDato),
    ("UM de Eclipse negativas", {"x": "10", "y": "10", "ssd": "90", "prof": "10", "um_planeador": "-5"}, None, None, motor.FaltaDato),
    ("un lado en cero", {"x": "0", "y": "10", "ssd": "90", "prof": "10"}, None, None, motor.FaltaDato),
    ("un solo lado efectivo", {"x": "10", "y": "10", "ssd": "90", "prof": "10", "x_ef": "5"}, None, None, motor.FaltaDato),
]


@pytest.mark.parametrize("nombre, valores, cuna, orientacion, clase", MOTIVOS, ids=[m[0] for m in MOTIVOS])
def test_lo_que_no_se_puede_calcular_muestra_el_motivo_del_motor_tal_cual_y_ningun_numero(p, datos_reales, nombre, valores, cuna, orientacion, clase):
    escribir(p, dict({"dosis": "200"}, **valores), cuna, orientacion)
    calcular_con_enter(p, "x")
    with pytest.raises(clase) as fallo:
        motor.calcular(datos_reales, pantalla.entrada_desde_textos(dict({"dosis": "200", "tf": "1.000"}, **valores), cuna, orientacion))
    assert p.etiqueta_motivo.text() == str(fallo.value) and p.etiqueta_motivo.isVisibleTo(p)
    assert sin_numero(p)


def test_falta_un_perfil_pide_el_oar(app, fabrica, monkeypatch, datos_reales):
    servicio_falso(monkeypatch, {(EQUIPO, ENERGIA): (3, dataclasses.replace(datos_reales, perfiles=None))})
    p = fabrica()
    escribir(p, {"dosis": "200", "x": "20", "y": "20", "ssd": "90", "prof": "10", "punto_x": "5"})
    calcular_con_enter(p)
    assert p.etiqueta_motivo.text() == "No hay perfiles cargados: escriba el OAR a mano" and sin_numero(p)
    escribir(p, {"dosis": "200", "x": "20", "y": "20", "ssd": "90", "prof": "10", "punto_x": "5", "oar_manual": "1.02"})
    calcular_con_enter(p)
    assert p.resultado is not None and dict((f[0], f[2]) for f in celdas(p.tabla_desglose))["OAR"] == "manual"


@pytest.mark.parametrize("campo", pantalla.CAMPOS, ids=lambda c: c.clave)
def test_la_clase_de_lo_raro_en_la_pantalla_da_el_motivo_y_ningun_numero(p, campo):
    """Por la pantalla, todos los campos por todas las entradas raras: el motivo es el de la lectura, nunca un error inesperado y nunca un número."""
    for raro in RAROS + (DEMASIADAS_CIFRAS,):
        escribir(p, dict(BASE, **{campo.clave: raro}), por_teclado=False)
        p.calcular()
        with pytest.raises(motor.FaltaDato) as fallo:
            pantalla.leer_numero(raro, campo)
        assert p.etiqueta_motivo.text() == str(fallo.value), raro
        assert sin_numero(p), raro


@pytest.mark.parametrize("campo", pantalla.CAMPOS, ids=lambda c: c.clave)
def test_numeros_bien_escritos_pero_imposibles_dan_numero_o_motivo_nunca_un_error_inesperado(p, datos_reales, campo):
    for texto in ("0", "-1", "-0.0001", "0.0001", "1", "12", "99999", "140.0000001", "59.99"):
        escribir(p, {**BASE, **({"x_ef": "5", "y_ef": "5"} if campo.clave in ("x_ef", "y_ef") else {}), campo.clave: texto}, por_teclado=False)
        p.calcular()
        assert "inesperado" not in p.etiqueta_motivo.text(), (texto, p.etiqueta_motivo.text())
        try:
            directo = motor.calcular(datos_reales, pantalla.entrada_desde_textos(p.textos(), None, None))
        except motor.NoCalculable as fallo:
            assert p.etiqueta_motivo.text() == str(fallo) and sin_numero(p), texto
        else:
            assert p.resultado == directo and p.etiqueta_um.text() == pantalla.texto_de_las_um(directo), texto


def test_un_error_que_no_es_un_motivo_se_dice_y_no_deja_numero(p, monkeypatch):
    def roto(datos, e):
        raise ZeroDivisionError("division by zero")
    monkeypatch.setattr(motor, "calcular", roto)
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == "El cálculo falló por un error inesperado (ZeroDivisionError: division by zero). Avise a quien mantiene la app." and sin_numero(p)


# ================================================================================================================================== la pantalla: sin tablas, el haz y su caché

def test_sin_tablas_lo_dice_al_abrir_y_al_calcular(bd_vacia, fabrica):
    p = fabrica()
    assert p.aviso_tablas.isVisibleTo(p) and p.aviso_tablas.text() == pantalla.texto_sin_tablas(EQUIPO)
    assert p.combo_energia.count() == 0 and not p.combo_energia.isEnabled()
    assert [p.combo_cuna.itemText(i) for i in range(p.combo_cuna.count())] == [pantalla.SIN_CUNA]
    escribir(p, BASE)
    calcular_con_enter(p)
    assert p.etiqueta_motivo.text() == pantalla.texto_sin_tablas(EQUIPO) and sin_numero(p)


def test_con_tablas_del_600_el_ix_dice_que_le_faltan(p):
    assert not p.aviso_tablas.isVisibleTo(p) and p.combo_energia.currentText() == ENERGIA
    assert [p.combo_cuna.itemText(i) for i in range(p.combo_cuna.count())] == [pantalla.SIN_CUNA, "15°", "30°", "45°", "60°"]
    p.combo_equipo.setCurrentIndex(p.combo_equipo.findText("Clinac iX"))
    assert p.aviso_tablas.isVisibleTo(p) and p.aviso_tablas.text() == pantalla.texto_sin_tablas("Clinac iX")
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == pantalla.texto_sin_tablas("Clinac iX") and sin_numero(p)


def test_la_lista_de_cunas_sale_por_angulo_y_no_en_el_orden_en_que_llegaron(app, fabrica, monkeypatch, datos_reales):
    """El físico ve las cuñas de menor a mayor ángulo, sea cual sea el orden en que el servicio las entrega."""
    desordenadas = {angulo: datos_reales.cunas[angulo] for angulo in (45, 15, 60, 30)}
    servicio_falso(monkeypatch, {(EQUIPO, ENERGIA): (1, dataclasses.replace(datos_reales, cunas=desordenadas))})
    p = fabrica()
    assert [p.combo_cuna.itemText(i) for i in range(p.combo_cuna.count())] == [pantalla.SIN_CUNA, "15°", "30°", "45°", "60°"]
    assert [p.combo_cuna.itemData(i) for i in range(p.combo_cuna.count())] == [None, 15, 30, 45, 60]


def test_el_aviso_de_sin_tablas_no_manda_a_un_boton_que_no_se_puede_usar(bd_vacia, fabrica):
    """El físico que abre la pestaña sin tablas lee el aviso: si nombrara el botón «Cargar tablas» (deshabilitado hasta la próxima entrega) lo mandaría a un control que no responde. El aviso y el
    motivo al calcular dicen lo mismo que la ayuda del botón: que la carga llega después y quién la hace."""
    p = fabrica()
    assert p.aviso_tablas.isVisibleTo(p) and not p.boton_cargar.isEnabled()
    aviso = p.aviso_tablas.text()
    assert p.boton_cargar.toolTip() in aviso and "próxima entrega" in aviso and "el físico jefe o el administrador" in aviso and "«Cargar tablas»" not in aviso
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == aviso and sin_numero(p)


def test_los_equipos_son_los_de_la_calculadora_en_la_forma_del_lector(p):
    """La pantalla tiene su tupla (UM.3 v2 retiró la del servicio); cada uno es su propia forma canónica para el lector, que es lo que guarda y busca el servicio."""
    assert [p.combo_equipo.itemText(i) for i in range(p.combo_equipo.count())] == list(pantalla.EQUIPOS) == ["Clinac 600", "Clinac iX"]
    assert all(lector.clave_equipo(e) == e for e in pantalla.EQUIPOS)


def test_lo_guardado_que_no_se_puede_usar_se_dice_y_no_hay_numero(app, fabrica, monkeypatch):
    servicio_falso(monkeypatch, {(EQUIPO, ENERGIA): (1, None)})

    def danado(equipo, energia):
        raise um_datos_haz.DatosHazError(f"Las tablas guardadas de {equipo}, {energia} no se pueden usar: el archivo «x» guardado no coincide con su huella")
    monkeypatch.setattr(um_datos_haz, "datos_del_haz", danado)
    p = fabrica()
    texto = "Las tablas guardadas de Clinac 600, 6 MV no se pueden usar: el archivo «x» guardado no coincide con su huella"
    assert p.aviso_tablas.text() == texto and p.aviso_tablas.isVisibleTo(p)
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == texto and sin_numero(p)


@pytest.mark.parametrize("falta", ["vigente", "datos_del_haz"])
def test_una_energia_que_ya_no_tiene_conjunto_vigente_lo_dice(app, fabrica, monkeypatch, datos_reales, falta):
    """Entre listar las energías y leer el haz otro equipo pudo anular el conjunto: la pantalla lo dice con su texto y no da número (ni un error suelto)."""
    servicio_falso(monkeypatch, {(EQUIPO, ENERGIA): (5, datos_reales)})
    p = fabrica()
    monkeypatch.setattr(um_datos_haz, falta, lambda equipo, energia: None)
    p._haces.clear()
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == "Ya no hay tablas vigentes del Clinac 600, 6 MV." and sin_numero(p)


def test_un_fallo_al_leer_la_base_se_dice_con_su_texto(app, fabrica, monkeypatch):
    def cae(*a):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(um_datos_haz, "energias_cargadas", cae)
    p = fabrica()
    assert p.aviso_tablas.text() == "No se pudieron leer las tablas guardadas del Clinac 600: database is locked"
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == p.aviso_tablas.text() and sin_numero(p)


@pytest.mark.parametrize("cual", ["vigente", "datos_del_haz"])
def test_un_fallo_de_la_base_al_leer_el_haz_se_dice_y_no_cae_a_otro_haz(app, fabrica, monkeypatch, datos_reales, cual):
    """La base puede fallar al CALCULAR (otro equipo guardando, la carpeta de red caída), no solo al listar las energías: se dice con su texto y no hay número."""
    servicio_falso(monkeypatch, {(EQUIPO, ENERGIA): (5, datos_reales)})
    p = fabrica()
    p._haces.clear()

    def cae(*a):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(um_datos_haz, cual, cae)
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == "No se pudieron leer las tablas guardadas del Clinac 600, 6 MV: database is locked" and sin_numero(p)


def test_el_haz_se_arma_una_vez_por_conjunto_y_otra_vez_si_cambia(app, fabrica, monkeypatch, datos_reales):
    """Trampa 10: un diccionario de la pantalla por `id` del conjunto vigente, sin caché global. Una carga nueva (otro `id`) se vuelve a leer, y el resultado calculado con las tablas
    anteriores no se queda: se dice que cambiaron."""
    haces = {(EQUIPO, ENERGIA): (11, datos_reales)}
    llamadas = servicio_falso(monkeypatch, haces)
    p = fabrica()
    escribir(p, BASE)
    for _ in range(3):
        p.calcular()
        assert p.resultado is not None
    assert llamadas == [(EQUIPO, ENERGIA)] and list(p._haces) == [11]
    haces[(EQUIPO, ENERGIA)] = (12, dataclasses.replace(datos_reales, cunas={}))
    p.calcular()
    assert p.etiqueta_motivo.text().startswith("Las tablas de este haz cambiaron") and sin_numero(p)
    assert [p.combo_cuna.itemText(i) for i in range(p.combo_cuna.count())] == [pantalla.SIN_CUNA]
    p.calcular()
    assert p.resultado is not None and llamadas == [(EQUIPO, ENERGIA)] * 2 and sorted(p._haces) == [11, 12]
    assert pantalla.CalculadoraUM.__init__.__code__.co_names.count("lru_cache") == 0 and "lru_cache" not in open(pantalla.__file__, encoding="utf-8").read()


def _lecturas_que_fallan(monkeypatch, datos_reales, fallan):
    """El servicio falso con el conjunto 5 y `vigente` con `database is locked` en las lecturas cuyo número (1 es la de abrir la pestaña) está en `fallan`."""
    servicio_falso(monkeypatch, {(EQUIPO, ENERGIA): (5, datos_reales)})
    real = um_datos_haz.vigente
    cuenta = []

    def a_veces(equipo, energia):
        cuenta.append(1)
        if len(cuenta) in fallan:
            raise sqlite3.OperationalError("database is locked")
        return real(equipo, energia)
    monkeypatch.setattr(um_datos_haz, "vigente", a_veces)
    return cuenta


FALLO_DE_LECTURA = "No se pudieron leer las tablas guardadas del Clinac 600, 6 MV: database is locked"


def test_un_fallo_pasajero_al_abrir_no_se_dice_como_un_cambio_de_las_tablas(app, fabrica, monkeypatch, datos_reales):
    """La base ocupada un instante al abrir la pestaña y libre al pulsar Calcular: las tablas NO cambiaron (es el mismo conjunto, el 5). El motivo dice lo que pasó, la lista de cuñas se llena (ahora
    se puede elegir una: por eso se pide revisarla) y el siguiente Calcular da el número. Nunca un número con una cuña que no se pudo elegir."""
    _lecturas_que_fallan(monkeypatch, datos_reales, {1})
    p = fabrica()
    assert p.aviso_tablas.text() == FALLO_DE_LECTURA and p._id_del_haz is None
    assert [p.combo_cuna.itemText(i) for i in range(p.combo_cuna.count())] == [pantalla.SIN_CUNA]
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == TABLAS_NO_LEIDAS and "cambiaron" not in p.etiqueta_motivo.text() and sin_numero(p)
    assert [p.combo_cuna.itemText(i) for i in range(p.combo_cuna.count())] == [pantalla.SIN_CUNA, "15°", "30°", "45°", "60°"]
    assert not p.aviso_tablas.isVisibleTo(p) and p._id_del_haz == 5
    p.calcular()
    assert p.resultado == motor.calcular(datos_reales, pantalla.entrada_desde_textos(BASE, None, None)) and p.resultado is not None


def test_si_la_relectura_tambien_falla_el_motivo_es_ese_fallo_y_no_otra_cosa(app, fabrica, monkeypatch, datos_reales):
    """Falla al abrir (1) y otra vez al volver a leer dentro de `calcular` (3): ni «cambiaron» ni «ya se leyeron»; el motivo es el fallo, el mismo del aviso de arriba. Luego la base responde: «no se
    habían podido leer», y al tercer Calcular el número."""
    _lecturas_que_fallan(monkeypatch, datos_reales, {1, 3})
    p = fabrica()
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == FALLO_DE_LECTURA == p.aviso_tablas.text() and p.aviso_tablas.isVisibleTo(p) and p._id_del_haz is None and sin_numero(p)
    p.calcular()
    assert p.etiqueta_motivo.text() == TABLAS_NO_LEIDAS and sin_numero(p) and p._id_del_haz == 5
    p.calcular()
    assert p.resultado is not None


# ================================================================================================================================== la pantalla: lo que borra el resultado y lo que no

def _con_resultado(p, um_planeador="296"):
    escribir(p, dict(BASE, um_planeador=um_planeador))
    calcular_con_enter(p)
    assert p.resultado is not None
    return p.resultado


def test_cambiar_de_equipo_borra_el_resultado(p):
    _con_resultado(p)
    p.combo_equipo.setCurrentIndex(1)
    assert sin_numero(p)


def test_cambiar_de_energia_borra_el_resultado(app, fabrica, monkeypatch, datos_reales):
    servicio_falso(monkeypatch, {(EQUIPO, "6 MV"): (1, datos_reales), (EQUIPO, "10 MV"): (2, dataclasses.replace(datos_reales, energia="10 MV"))})
    p = fabrica()
    assert [p.combo_energia.itemText(i) for i in range(p.combo_energia.count())] == ["6 MV", "10 MV"]
    _con_resultado(p)
    p.combo_energia.setCurrentIndex(1)
    assert sin_numero(p) and p._id_del_haz == 2


@pytest.mark.parametrize("clave", [c.clave for c in pantalla.CAMPOS])
def test_cambiar_lo_escrito_en_cualquier_campo_borra_el_resultado(p, clave):
    _con_resultado(p)
    QTest.keyClicks(p.campos[clave], "1")
    assert sin_numero(p)


def test_cambiar_la_cuna_o_su_orientacion_borra_el_resultado(p):
    _con_resultado(p)
    p.combo_cuna.setCurrentIndex(1)
    assert sin_numero(p) and p.combo_orientacion.isEnabled()
    p.combo_orientacion.setCurrentIndex(p.combo_orientacion.findData("IN"))
    calcular_con_enter(p)
    assert p.resultado is not None
    p.combo_orientacion.setCurrentIndex(p.combo_orientacion.findData("OUT"))
    assert sin_numero(p)
    calcular_con_enter(p)
    p.combo_cuna.setCurrentIndex(0)
    assert sin_numero(p) and not p.combo_orientacion.isEnabled() and p.combo_orientacion.currentData() is None


def test_con_cuna_la_pantalla_no_supone_la_orientacion_y_calcula_con_la_elegida(p, datos_reales):
    """UM4-D5 por el camino del físico. Elegir la cuña NO elige su orientación (la lista sigue en «Elija la orientación»); sin elegirla, Enter da el motivo de la capa pura y ningún número (nunca
    las UM de una orientación que el físico no eligió); y la elegida es la que llega al motor: en un campo que no es cuadrado IN/OUT y LEFT/RIGHT dan UM distintas."""
    valores = dict(BASE, x="20", y="10", ssd="90")
    escribir(p, valores, cuna=15)
    assert p.combo_orientacion.isEnabled() and p.combo_orientacion.currentData() is None and p.combo_orientacion.currentText() == pantalla.ELIJA_ORIENTACION
    calcular_con_enter(p)
    with pytest.raises(motor.FaltaDato) as motivo:
        pantalla.entrada_desde_textos(valores, 15, None)
    assert p.etiqueta_motivo.text() == str(motivo.value) and p.etiqueta_motivo.isVisibleTo(p) and sin_numero(p)
    um = {}
    for orientacion in motor.ORIENTACIONES:
        p.combo_orientacion.setCurrentIndex(p.combo_orientacion.findData(orientacion))
        assert sin_numero(p)
        calcular_con_enter(p)
        directo = motor.calcular(datos_reales, pantalla.entrada_desde_textos(valores, 15, orientacion))
        assert p.resultado == directo and p.etiqueta_um.text() == pantalla.texto_de_las_um(directo) and not p.etiqueta_motivo.isVisibleTo(p), orientacion
        um[orientacion] = p.etiqueta_um.text()
    assert um["IN"] == um["OUT"] != um["LEFT"] == um["RIGHT"]
    p.combo_orientacion.setCurrentIndex(0)
    calcular_con_enter(p)
    assert p.etiqueta_motivo.text() == str(motivo.value) and sin_numero(p)


def test_los_umbrales_cambian_el_estado_y_no_las_um_ni_el_error(p):
    QTest.keyClicks(p.umbrales["dentro"], "5")        # sin resultado, cambiar un umbral no muestra nada
    assert sin_numero(p) and p.etiqueta_estado.text() == "" and p.etiqueta_error.text() == ""
    p.umbrales["dentro"].setText("2")
    r = _con_resultado(p, um_planeador=f"{302.1148036253776 / 1.025:.4f}")
    antes = (p.etiqueta_um.text(), p.etiqueta_d_um.text(), p.etiqueta_error.text(), celdas(p.tabla_desglose), avisos_de(p))
    assert p.etiqueta_estado.text() == "Estado: Revisar" and p.etiqueta_error.text() == pantalla.texto_del_error(r.error_pct, (2.0, 3.0))
    for dentro, fuera, estado in (("3", "4", "Estado: Dentro"), ("1", "2", "Estado: Fuera"), ("2", "3", "Estado: Revisar"),
                                  ("3", "2", "Estado sin evaluar: " + REGLA_DEL_MOTOR + "3.0 y 2.0")):
        for clave, texto in (("dentro", dentro), ("fuera", fuera)):
            p.umbrales[clave].selectAll()
            QTest.keyClick(p.umbrales[clave], Qt.Key_Delete)
            QTest.keyClicks(p.umbrales[clave], texto)
        assert p.etiqueta_estado.text() == estado
        assert (p.etiqueta_um.text(), p.etiqueta_d_um.text(), celdas(p.tabla_desglose), avisos_de(p)) == (antes[0], antes[1], antes[3], antes[4]) and p.resultado is r
    assert p.etiqueta_error.text() == pantalla.texto_del_error(r.error_pct, ())


def escribir_umbrales(p, dentro, fuera):
    for clave, texto in (("dentro", dentro), ("fuera", fuera)):
        p.umbrales[clave].selectAll()
        QTest.keyClick(p.umbrales[clave], Qt.Key_Delete)
        QTest.keyClicks(p.umbrales[clave], texto)


@pytest.mark.parametrize("orden", ["umbrales_primero", "umbrales_despues"])
@pytest.mark.parametrize("dentro, fuera, error, estado", [("2.5", "4", 2.5004, "Revisar"), ("2.5", "4", -2.5004, "Revisar"), ("2", "3.5", 3.5004, "Fuera"), ("1.5", "2.5", 2.4996, "Revisar")])
def test_la_pantalla_escribe_el_error_con_las_cifras_que_piden_los_umbrales_escritos(p, datos_reales, orden, dentro, fuera, error, estado):
    """UM4-D6: con Dentro = 2.5 escrito, un error de 2.5004 [%] no puede leerse «+2.50» (igual que el umbral) junto a «Estado: Revisar»: las cifras del error salen de los umbrales ESCRITOS, también
    cuando se escriben después de calcular, y no de los de omisión (2 y 3). La UM de Eclipse se construye para que el error sea el pedido (verdad conocida, sin el motor)."""
    um = motor.calcular(datos_reales, entrada(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0)).um
    if orden == "umbrales_primero":
        escribir_umbrales(p, dentro, fuera)
    _con_resultado(p, um_planeador=repr(um / (1 + error / 100)))
    if orden == "umbrales_despues":
        escribir_umbrales(p, dentro, fuera)
    assert p.resultado.error_pct == pytest.approx(error, abs=1e-9)
    assert p.etiqueta_error.text() == f"Error frente a Eclipse: {error:+.4f} [%]" != f"Error frente a Eclipse: {error:+.2f} [%]"
    assert p.etiqueta_estado.text() == f"Estado: {estado}" == f"Estado: {motor.estado_de(p.resultado.error_pct, float(dentro), float(fuera))}"


def test_en_la_frontera_del_2_por_ciento_el_texto_tiene_las_cifras_que_hacen_falta(p, datos_reales):
    um = motor.calcular(datos_reales, entrada(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0)).um
    for planeador, estado in ((um / 1.02004, "Revisar"), (um / 1.01996, "Dentro"), (um / 1.03003, "Fuera")):
        _con_resultado(p, um_planeador=repr(planeador))
        assert p.etiqueta_estado.text() == f"Estado: {estado}" == f"Estado: {motor.estado_de(p.resultado.error_pct)}"
        assert p.etiqueta_error.text() == pantalla.texto_del_error(p.resultado.error_pct, (2.0, 3.0))
        assert p.etiqueta_error.text() not in ("Error frente a Eclipse: +2.00 [%]", "Error frente a Eclipse: +3.00 [%]")


def test_con_um_de_eclipse_el_error_es_el_del_motor(p):
    r = _con_resultado(p, um_planeador="296")
    assert r.error_pct == pytest.approx(100 * (r.um - 296) / 296)
    assert p.etiqueta_error.text() == f"Error frente a Eclipse: {r.error_pct:+.2f} [%]" and p.etiqueta_estado.text() == "Estado: Revisar"


def test_los_avisos_se_ven_todos_y_en_su_orden(p, datos_reales):
    valores = {"dosis": "200", "x": "4", "y": "3", "x_ef": "3", "y_ef": "2.6", "ssd": "125", "prof": "1"}
    escribir(p, valores)
    calcular_con_enter(p)
    directo = motor.calcular(datos_reales, pantalla.entrada_desde_textos(dict({"tf": "1.000"}, **valores), None, None))
    assert len(directo.avisos) >= 6 and avisos_de(p) == list(directo.avisos) and p.titulo_avisos.text() == f"Avisos ({len(directo.avisos)})"


# ================================================================================================================================== la pantalla: teclado, textos, copiar

def test_enter_en_cualquier_campo_o_umbral_calcula(p):
    for linea in list(p.campos.values()) + list(p.umbrales.values()):
        escribir(p, BASE)
        assert sin_numero(p)
        QTest.keyClick(linea, Qt.Key_Return)
        assert p.resultado is not None


def test_el_orden_de_tabulacion_es_el_de_lectura(p):
    widgets = [{"cuna": p.combo_cuna, "cuna_orientacion": p.combo_orientacion}.get(c, p.campos.get(c)) for c in pantalla.ORDEN]
    widgets += [p.boton_calcular, p.umbrales["dentro"], p.umbrales["fuera"]]
    vistos, w = [], widgets[0]
    for _ in range(200):
        if w in widgets and w not in vistos:
            vistos.append(w)
        w = w.nextInFocusChain()
    assert vistos == widgets
    assert pantalla.ORDEN == ("dosis", "x", "y", "centro_x", "centro_y", "x_ef", "y_ef", "ssd", "prof", "prof_ef", "punto_x", "punto_y", "oar_manual", "cuna", "cuna_orientacion",
                              "wf_manual", "tf", "um_planeador")


def test_etiquetas_con_unidades_entre_corchetes_y_opcionales_marcados(p):
    for campo in pantalla.CAMPOS:
        linea = p.campos[campo.clave]
        assert linea.placeholderText().startswith("opcional") == (not campo.obligatorio), campo.clave
        assert linea.toolTip() == campo.explicacion and (linea.toolTip().startswith("Opcional.") == (not campo.obligatorio))
    unidades = {"dosis": "[cGy]", "x": "[cm]", "y": "[cm]", "centro_x": "[cm]", "centro_y": "[cm]", "x_ef": "[cm]", "y_ef": "[cm]", "ssd": "[cm]", "prof": "[cm]", "prof_ef": "[cm]",
                "punto_x": "[cm]", "punto_y": "[cm]", "um_planeador": "[UM]"}
    for campo in pantalla.CAMPOS:
        assert (unidades.get(campo.clave, "") in campo.etiqueta) and (campo.etiqueta.count("[") == (1 if campo.clave in unidades else 0)), campo.clave


def _todos_los_textos(p):
    textos = [w.text() for w in p.findChildren((QLabel, QAbstractButton, QLineEdit))]
    textos += [w.toolTip() for w in p.findChildren(QWidget)] + [w.placeholderText() for w in p.campos.values()]
    textos += [p.subpestanas.tabText(i) for i in range(p.subpestanas.count())] + [t for par in pantalla.INFO for t in par]
    return textos


def test_ningun_texto_de_la_pantalla_lleva_simbolos_ni_unidades_entre_parentesis(p):
    _con_resultado(p)
    for texto in _todos_los_textos(p) + avisos_de(p):
        assert not SIMBOLOS.search(texto.replace(" × ", " x ")), texto
        assert not ENTRE_PARENTESIS.search(texto), texto
    for nombre in dir(pantalla):
        valor = getattr(pantalla, nombre)
        if isinstance(valor, str) and nombre.isupper():
            assert not SIMBOLOS.search(valor.replace(" × ", " x ")) and not ENTRE_PARENTESIS.search(valor), nombre


def test_copiar_el_desglose(p):
    assert not p.boton_copiar.isEnabled()
    QApplication.clipboard().setText("antes")
    p.copiar()                                      # sin resultado no hay nada que copiar: el portapapeles no cambia (la guarda de dentro; el botón ya está deshabilitado)
    assert QApplication.clipboard().text() == "antes"
    r = _con_resultado(p)
    QApplication.clipboard().setText("")
    QTest.mouseClick(p.boton_copiar, Qt.LeftButton)
    primera, resto = QApplication.clipboard().text().split("\n", 1)      # la primera línea es el contexto (UM4-D11, abajo); lo demás, el desglose de siempre
    assert resto == pantalla.texto_para_copiar(r) and primera.startswith("Equipo: ")


def test_el_desglose_se_puede_seleccionar_y_no_editar(p):
    _con_resultado(p)
    t = p.tabla_desglose
    assert t.editTriggers() == t.NoEditTriggers and t.selectionMode() != t.NoSelection
    assert all(t.item(i, j).toolTip() == t.item(i, j).text() for i in range(t.rowCount()) for j in range(t.columnCount()))


def test_cargar_tablas_esta_y_espera_su_entrega_y_la_parte_json_tambien(p):
    assert p.boton_cargar.text() == "Cargar tablas" and not p.boton_cargar.isEnabled() and p.boton_cargar.toolTip() == pantalla.CARGAR_TABLAS_LLEGA_DESPUES
    assert "el físico jefe o el administrador" in p.boton_cargar.toolTip()
    assert [p.subpestanas.tabText(i) for i in range(p.subpestanas.count())] == ["Manual", "Desde JSON"]
    assert p.subpestanas.widget(1).text() == pantalla.LA_JSON_LLEGA_DESPUES and p.subpestanas.currentIndex() == 0
    assert not re.search(r"UM\.\d|DC\d|DA-\d|DP-\d", " ".join(_todos_los_textos(p))), "sin ids internos en lo que ve el físico"


# ================================================================================================================================== Info y la ecuación

TEMAS = {"La ecuación": ("ecuación 3 de la TG-71", "PDD_N", "SSD fija", "isocéntricos", "Con profundidad efectiva", "((SSD + d_ef)/(SSD + d))²", "su valor y su origen"),
         "El factor de campo (OF) compila Sc y Sp": ("Sc", "Sp", "cabezal", "maniquí", "SSD 100 [cm]", "5 [cm]"),
         "Cuándo se corrige": ("ecuación 14", "sin tablas de TPR", "cuadrado equivalente del campo efectivo", "el Sc se lleva al de las mandíbulas con su intercambio X/Y",
                               "Sc(rc)/Sc(lectura)", "tabla IV", "vale 1",
                               "Sin curva, la corrección está apagada, también el intercambio X/Y", "con su origen"),
         "Tres campos": ("(rc)", "(r)", "(rd0)", "ecuación 14 completa", "lectura alterna", "encima del desglose, en la línea «Campos»"),
         "D'0": ("dmax", "d0", "con su origen", "máximo medido"),
         "PDD_N": ("normalizado en d0", "Mayneord"),
         "De dónde sale el OAR": ("perfiles de campo abierto", "Sobre el eje", "2 [%]", "10 [cm]", "perfil primario", "sobre el eje"),
         "La cuña": ("15°", "por confirmar", "30°, 45° y 60°", "a mano", "independiente de la SSD", "IN u OUT", "LEFT o RIGHT", "rectángulo efectivo tal como se escribió",
                     "siempre se elige", "su valor y los dos datos"),
         "Tolerancia": ("TG-71", "TG-114", "2 a 5 [%]", "Dentro hasta 2 [%]", "Fuera más de 3 [%]", "no las UM"),
         "Lo que no cubre": ("IMRT", "VMAT", "electrones", "cuñas dinámicas", "láminas", "dosis real del campo en el punto", "muy alargados", "último tramo medido del PDD",
                             "No se guarda")}


def test_info_no_es_modal_y_dice_cada_tema_por_su_texto(p):
    assert p.dialogo_info is None
    QTest.mouseClick(p.boton_info, Qt.LeftButton)
    d = p.dialogo_info
    assert d is not None and d.isVisible() and not d.isModal() and d.windowModality() == Qt.NonModal and d.parent() is p
    assert d.windowTitle() == pantalla.TITULO_DE_LA_INFO
    textos = dict(d.textos())
    assert list(textos) == list(TEMAS)
    for tema, claves in TEMAS.items():
        for clave in claves:
            assert clave in textos[tema], (tema, clave)
    assert d.textos() == list(pantalla.INFO)
    _con_resultado(p)                                             # no bloquea la pestaña
    QTest.mouseClick(p.boton_info, Qt.LeftButton)
    assert p.dialogo_info is d and d.isVisible()


def test_info_se_destruye_con_la_pestana(bd, app):
    p = pantalla.CalculadoraUM("jefa")
    p.mostrar_info()
    d = p.dialogo_info
    cerrar(p)
    assert sip.isdeleted(d)


def test_la_ecuacion_se_dibuja_sin_pyplot_y_sin_dejar_figuras(p):
    import matplotlib
    from matplotlib import _pylab_helpers
    backend = dict.__getitem__(matplotlib.rcParams, "backend")
    figuras = _pylab_helpers.Gcf.get_num_fig_managers()
    q = pantalla.CalculadoraUM("jefa")
    try:
        assert q.ecuacion.pixmap() is not None and not q.ecuacion.pixmap().isNull() and q.ecuacion.toolTip() == pantalla.ECUACION_TEXTO
        assert dict.__getitem__(matplotlib.rcParams, "backend") == backend and _pylab_helpers.Gcf.get_num_fig_managers() == figuras
    finally:
        cerrar(q)
    arbol = ast.parse(open(pantalla.__file__, encoding="utf-8").read())
    modulos = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
    assert not {m for m in modulos if m and ("pyplot" in m or m in ("sqlite3", "data.ManejoDatos.conection") or m.startswith("data."))}, modulos
    assert {"matplotlib.figure", "matplotlib.backends.backend_agg"} <= modulos


def test_si_matplotlib_falla_queda_la_ecuacion_en_texto(bd, app, monkeypatch):
    import matplotlib.backends.backend_agg as agg

    class Roto:
        def __init__(self, *a, **k):
            raise RuntimeError("sin fuentes")
    monkeypatch.setattr(agg, "FigureCanvasAgg", Roto)
    assert pantalla.dibujar_ecuacion() is None
    q = pantalla.CalculadoraUM("jefa")
    try:
        assert q.ecuacion.text() == pantalla.ECUACION_TEXTO and (q.ecuacion.pixmap() is None or q.ecuacion.pixmap().isNull())
    finally:
        cerrar(q)


def test_la_pestana_se_arma_rapido(bd, app):
    """Carga diferida: abrir la pestaña debe ser breve (medido en el pre-vuelo: unos 0.2 [s] con matplotlib ya cargado; el tope deja margen para una máquina cargada)."""
    import time
    t = time.perf_counter()
    q = pantalla.CalculadoraUM("jefa")
    dura = time.perf_counter() - t
    cerrar(q)
    assert dura < 3.0


# ================================================================================================================================== la ventana principal y el empaquetado

PREVIAS = ["600", "iX", "Halcyon", "Braquiterapia", "Tomógrafo", "Equipos", "Excel", "Registros", "Visor BD", "Usuarios", "Referencias"]


@pytest.fixture
def bd_arrancada(plantilla, monkeypatch, tmp_path):
    """Una copia de la base cargada, abierta con el arranque REAL de la app (como `tests/test_c2_pestana_referencias_en_mainwindow.py`): la ventana principal la necesita."""
    ruta = str(tmp_path / "arrancada.db")
    shutil.copy(plantilla, ruta)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def test_la_pestana_va_al_final_y_carga_la_pantalla_real(bd_arrancada, app):
    from data.ManejoDatos.user import Usuario
    from ui.mainpages import MainWindow
    w = MainWindow(Usuario(username="jefa", fullname="Jefa de Física"))
    try:
        assert [w.tabs.tabText(i) for i in range(w.tabs.count())] == PREVIAS + ["Calculadora UM"]
        assert [t for t, _ in w._tab_definiciones] == PREVIAS + ["Calculadora UM"]
        antes = set(w._tab_instancias)
        w._cargar_pestania_diferida(len(PREVIAS))
        assert set(w._tab_instancias) - antes == {len(PREVIAS)}
        pagina = w._tab_instancias[len(PREVIAS)]
        assert isinstance(pagina, pantalla.CalculadoraUM) and pagina.usuario is w.user_id
        assert pagina.combo_energia.currentText() == ENERGIA and not pagina.aviso_tablas.isVisibleTo(pagina)
    finally:
        cerrar(w, con_close=False)


SEIS = ("services.um_lector_eclipse", "services.um_motor", "services.um_plausibilidad", "services.um_armar", "services.um_datos_haz", "ui.paginasGuia.calculadora_um")


def _hidden_imports(texto):
    arbol = ast.parse(texto)
    lista = next(n.value for n in arbol.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "hidden_imports" for t in n.targets))
    return [e.value for e in lista.elts]


def _build_exe():
    return open(os.path.join(RAIZ, "build_exe.py"), "rb").read()


def test_si_la_pantalla_no_se_puede_crear_la_ventana_principal_sigue(bd_arrancada, app, monkeypatch, capsys):
    """El patrón de Referencias: una pantalla rota deja la pestaña vacía y lo dice en la consola; la ventana principal y las demás pestañas siguen."""
    from data.ManejoDatos.user import Usuario
    from ui.mainpages import MainWindow

    def rota(*a, **k):
        raise RuntimeError("pantalla rota")
    monkeypatch.setattr(pantalla, "CalculadoraUM", rota)
    w = MainWindow(Usuario(username="jefa", fullname="Jefa de Física"))
    try:
        w._cargar_pestania_diferida(len(PREVIAS))
        pagina = w._tab_instancias[len(PREVIAS)]
        assert type(pagina) is QWidget and "Error pestaña de la calculadora de UM: pantalla rota" in capsys.readouterr().out
        assert [w.tabs.tabText(i) for i in range(w.tabs.count())] == PREVIAS + ["Calculadora UM"]
    finally:
        cerrar(w, con_close=False)


def test_build_exe_sigue_en_crlf():
    crudo = _build_exe()
    assert b"\r\n" in crudo and b"\n" not in crudo.replace(b"\r\n", b""), "build_exe.py sigue en CRLF"


def test_build_exe_lista_los_seis_modulos_una_vez():
    nombres = _hidden_imports(_build_exe().decode("utf-8"))
    for modulo in SEIS:
        assert nombres.count(modulo) == 1, modulo
        assert os.path.exists(os.path.join(RAIZ, *modulo.split(".")) + ".py"), modulo


@pytest.mark.parametrize("modulo", SEIS)
def test_la_cuenta_de_build_exe_discrimina(modulo):
    """La prueba de arriba cae si uno de los seis falta o está dos veces (mutado EN MEMORIA: arnes reescribiría el archivo sin su CRLF)."""
    texto = _build_exe().decode("utf-8")
    linea = f'    "{modulo}",\r\n'
    assert texto.count(linea) == 1
    assert _hidden_imports(texto.replace(linea, "")).count(modulo) == 0
    assert _hidden_imports(texto.replace(linea, linea + linea)).count(modulo) == 2


# ================================================================================================================================== segunda pasada (10-11, auditoría independiente)
# Lo que la auditoría de cinco lentes halló en la pantalla ya corregida: una ventana que crece con lo que se escribe, textos de Info y de ayuda que no dicen toda la verdad, una cuña que se
# pierde al volver a leer las tablas, un aviso cortado, un aviso de «sin tablas» que sigue en pantalla, caracteres que no se ven, Enter sin respuesta en el botón y lo que se copia sin contexto.

def _pasos():
    """El bucle de eventos el tiempo que hace falta para que el diseño de lo mostrado se rehaga (un widget sin mostrar no recalcula sus mínimos)."""
    for _ in range(6):
        QApplication.sendPostedEvents()
        QApplication.processEvents()


def _teclear(linea, texto):
    """Como una persona: selecciona todo, borra y teclea (cada letra dispara `textEdited`)."""
    linea.selectAll()
    QTest.keyClick(linea, Qt.Key_Delete)
    QTest.keyClicks(linea, texto)


def _umbrales_de_omision(p):
    for clave, _, _, valor in pantalla.UMBRALES:
        p.umbrales[clave].setText(f"{valor:g}")


def _umbrales_escritos(dentro, fuera):
    def poner(p):
        _umbrales_de_omision(p)
        _con_resultado(p)
        _teclear(p.umbrales["dentro"], dentro)
        _teclear(p.umbrales["fuera"], fuera)
    return poner


def _campo_escrito(clave, texto):
    def poner(p):
        _umbrales_de_omision(p)
        escribir(p, dict(BASE, **{clave: texto}), por_teclado=False)
        p.calcular()
    return poner


def _cinco_motivos(p):
    _umbrales_de_omision(p)
    escribir(p, {}, por_teclado=False)
    p.calcular()
    assert p.etiqueta_motivo.text().count("\n") == 4


ANCHOS = {"umbral de Dentro vacío": _umbrales_escritos("", "3"), "umbral de Revisar con un porcentaje": _umbrales_escritos("2", "3%"),
          "Dentro 3 y Revisar 2": _umbrales_escritos("3", "2"), "Dentro 0": _umbrales_escritos("0", "3"), "400 nueves en TF": _campo_escrito("tf", "9" * 400),
          "400 nueves en la dosis": _campo_escrito("dosis", "9" * 400), "un token largo que no es un número": _campo_escrito("ssd", "z" * 400),
          "un motivo de cinco líneas": _cinco_motivos}


@pytest.mark.parametrize("escenario", list(ANCHOS))
def test_ningun_texto_de_la_pestana_ensancha_su_ancho_minimo(p, escenario):
    """E2: ni un umbral mal escrito mientras se reescribe, ni un campo con un token enorme, ni un motivo de varias líneas fijan un ancho mínimo según su texto: el mínimo de la pestaña (y el de su
    parte manual) no crece, o se queda por debajo de 1200 [px] (la ventana principal real mide 1194: por debajo de eso la pestaña no la empuja)."""
    p.resize(1400, 700)
    p.show()
    manual = p.subpestanas.widget(0)
    _pasos()
    base = (p.minimumSizeHint().width(), manual.minimumSizeHint().width())
    ANCHOS[escenario](p)
    _pasos()
    assert p.minimumSizeHint().width() <= max(base[0], 1200) and manual.minimumSizeHint().width() <= max(base[1], 1200), (escenario, p.minimumSizeHint().width(), manual.minimumSizeHint().width(), base)


def test_la_ventana_principal_no_crece_con_ningun_texto_de_la_pestana(bd_arrancada, app, monkeypatch):
    """E2 en la ventana REAL, con la hoja de estilo de la app (cwd = el repositorio): su mínimo no crece, o se queda por debajo de 1200 [px]."""
    monkeypatch.chdir(RAIZ)
    from data.ManejoDatos.user import Usuario
    from ui.mainpages import MainWindow
    w = MainWindow(Usuario(username="jefa", fullname="Jefa de Física"))
    try:
        assert w.styleSheet(), "la ventana lleva la hoja de estilo real"
        w.showNormal()
        w.resize(1366, 768)
        w.tabs.setCurrentIndex(len(PREVIAS))
        if len(PREVIAS) not in w._tab_instancias:
            w._cargar_pestania_diferida(len(PREVIAS))
        pagina = w._tab_instancias[len(PREVIAS)]
        _pasos()
        base = w.minimumSizeHint().width()
        for escenario, preparar in ANCHOS.items():
            preparar(pagina)
            _pasos()
            assert w.minimumSizeHint().width() <= max(base, 1200) and pagina.minimumSizeHint().width() <= max(base, 1200), (escenario, w.minimumSizeHint().width(), pagina.minimumSizeHint().width(), base)
    finally:
        cerrar(w, con_close=False)


def test_toda_etiqueta_cuyo_texto_cambia_con_lo_escrito_o_con_el_resultado_se_ajusta_a_la_linea(p):
    """La CLASE (E2): cada `QLabel` de la pestaña cuyo texto cambia entre un estado y otro (UM, D/UM, error, estado, motivo, campos, aviso de tablas, título de los avisos) ajusta la línea y
    se reparte el ancho de su fila: ninguna lo fija según su texto."""
    etiquetas = p.findChildren(QLabel)
    fotos = [{e: e.text() for e in etiquetas}]
    for paso in (_umbrales_escritos("2", "3"), _umbrales_escritos("3", "2"), _cinco_motivos, lambda q: q.combo_equipo.setCurrentIndex(q.combo_equipo.findText("Clinac iX"))):
        paso(p)
        fotos.append({e: e.text() for e in etiquetas})
    dinamicas = [e for e in etiquetas if len({foto[e] for foto in fotos}) > 1]
    for esperada in (p.etiqueta_um, p.etiqueta_d_um, p.etiqueta_error, p.etiqueta_estado, p.etiqueta_motivo, p.etiqueta_campos, p.aviso_tablas, p.titulo_avisos):
        assert esperada in dinamicas
    for etiqueta in dinamicas:
        assert etiqueta.wordWrap() and etiqueta.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding, etiqueta.text()[:40]


def test_un_nombre_de_equipo_largo_no_ensancha_el_aviso_de_sin_tablas(bd_vacia, fabrica, monkeypatch):
    monkeypatch.setattr(pantalla, "EQUIPOS", ("Acelerador lineal de la sala de tratamiento número tres del segundo piso del edificio nuevo",))
    p = fabrica()
    assert pantalla.EQUIPOS[0] in p.aviso_tablas.text()
    assert p.aviso_tablas.minimumSizeHint().width() < 400


@pytest.mark.parametrize("campo", pantalla.CAMPOS, ids=lambda c: c.clave)
def test_el_texto_que_cita_un_motivo_de_lectura_se_acota(campo):
    """E2: un token pegado en un campo no ensancha la ventana por el motivo que lo cita: se citan los 30 primeros caracteres y «…» (con 30 o menos, el texto entero)."""
    for largo in ("9" * 400, "z" * 400):
        with pytest.raises(motor.FaltaDato) as fallo:
            pantalla.leer_numero(largo, campo)
        assert max(len(palabra) for palabra in str(fallo.value).split()) <= 50, str(fallo.value)[:120]
    with pytest.raises(motor.FaltaDato) as justo:
        pantalla.leer_numero("a" * 30, campo)
    with pytest.raises(motor.FaltaDato) as de_mas:
        pantalla.leer_numero("a" * 31, campo)
    assert "«" + "a" * 30 + "»" in str(justo.value) and "«" + "a" * 30 + "…»" in str(de_mas.value)
    with pytest.raises(motor.FaltaDato) as con_bordes:
        pantalla.leer_numero("   " + "a" * 30 + "   ", campo)
    assert "«" + "a" * 30 + "»" in str(con_bordes.value)      # los espacios de los bordes ni se citan ni cuentan en el límite


def _info(p):
    p.mostrar_info()
    return dict(p.dialogo_info.textos())


def test_el_tema_cuando_se_corrige_no_dice_que_la_correccion_vale_1_con_profundidad_efectiva(p):
    """FID-1: con profundidad efectiva el motor lee el PDD y el OF en d_ef y Sc(rc)/Sc(lectura) deja de valer 1 (con prof 15 y prof_ef 8: 0.9985); el texto ya no lo afirma."""
    tema = _info(p)["Cuándo se corrige"]
    assert "A la SSD de la tabla y sin láminas la corrección vale 1" not in tema
    assert "sin láminas y sin profundidad efectiva la corrección vale 1" in tema and "Con profundidad efectiva" in tema
    ayuda = p.campos["prof_ef"].toolTip()
    assert "campo de lectura del PDD y del factor de campo" in ayuda and "El OAR y el factor de cuña siguen" not in ayuda and "siguen en la profundidad física" in ayuda


def test_el_plano_del_punto_se_dice_en_la_ayuda_de_sus_dos_campos_y_en_el_tema_del_oar(p):
    """FID-2: el motor toma la posición del punto en el plano del isocentro y la proyecta a la profundidad: escribirla a la profundidad cambia las UM hasta 4 [%]."""
    for clave in ("punto_x", "punto_y"):
        ayuda = p.campos[clave].toolTip()
        assert "plano del isocentro (no a la profundidad del cálculo)" in ayuda and "vacío vale 0, el punto sobre el eje del haz" in ayuda and "el punto en el isocentro" not in ayuda
    assert "plano del isocentro (no a la profundidad del cálculo)" in _info(p)["De dónde sale el OAR"]


def test_la_ecuacion_nombra_todos_los_origenes_que_muestra_el_desglose(p):
    """FID-4a: el origen de cada factor es tabla, plan, cálculo o manual, y también «sin cuña», «sin bandeja» o «sobre el eje» cuando el factor vale 1: Info los nombra todos."""
    origenes = set()
    for valores, cuna, orientacion in ((BASE, None, None), (dict(BASE, tf="0.95"), None, None), (dict(BASE, punto_x="3"), None, None), (dict(BASE, ssd="90"), 15, "IN"),
                                       (dict(BASE, oar_manual="0.98", wf_manual="0.9"), None, None)):
        escribir(p, valores, cuna, orientacion)
        calcular_con_enter(p)
        assert p.resultado is not None
        origenes |= {fila[2] for fila in celdas(p.tabla_desglose)}
    assert {"tabla", "plan", "cálculo", "manual", "sin cuña", "sin bandeja", "sobre el eje"} <= origenes
    texto = _info(p)["La ecuación"]
    for origen in origenes:
        assert origen in texto, origen


def test_cada_campo_se_llama_igual_en_su_etiqueta_y_en_el_motivo_que_lo_nombra(p):
    """TP-4: la etiqueta dice «Punto X desde el eje [cm]» y el motivo decía «la posición X del punto respecto al eje [cm]»: el motivo usa las palabras de la etiqueta."""
    for campo in pantalla.CAMPOS:
        articulo, resto = campo.nombre.split(" ", 1)
        assert articulo in ("el", "la", "las") and resto.lower() == campo.etiqueta.lower(), campo.clave
    escribir(p, dict(BASE, punto_x="abc"))
    calcular_con_enter(p)
    assert p.etiquetas["punto_x"].text().lower() in p.etiqueta_motivo.text().lower() and sin_numero(p)


@pytest.mark.parametrize("tecla", [Qt.Key_Return, Qt.Key_Enter], ids=["Enter", "Enter del teclado numerico"])
@pytest.mark.parametrize("donde", ["boton_calcular", "combo_cuna", "combo_orientacion"])
def test_enter_calcula_tambien_con_el_foco_en_el_boton_y_en_las_listas_de_cuna_y_orientacion(p, donde, tecla):
    """EST-4: solo respondía la barra espaciadora. La lista de orientación solo se puede enfocar con cuña elegida."""
    escribir(p, BASE, 15, "IN")
    p.limpiar_resultado()
    assert sin_numero(p)
    QTest.keyClick(getattr(p, donde), tecla)
    assert p.resultado is not None and p.resultado == motor.calcular(p._haces[p._id_del_haz], pantalla.entrada_desde_textos(BASE, 15, "IN"))


TABLAS_APARECIERON = "Ahora hay tablas cargadas del Clinac 600. Elija la energía y la cuña y pulse Calcular otra vez."


def test_al_calcular_sin_tablas_se_vuelve_a_mirar_la_base_y_el_aviso_de_sin_tablas_no_se_queda(app, fabrica, monkeypatch, datos_reales):
    """EST-2: otro puesto cargó las tablas después de abrir la pestaña. Calcular mira otra vez (energías y haz) antes de decir que faltan: llena la lista, quita el aviso y pide elegir la
    energía y la cuña (nunca un número con una energía que nadie eligió)."""
    haces = {}
    servicio_falso(monkeypatch, haces)
    p = fabrica()
    assert p.aviso_tablas.text() == pantalla.texto_sin_tablas(EQUIPO) and p.combo_energia.count() == 0
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == pantalla.texto_sin_tablas(EQUIPO) and sin_numero(p)          # sigue sin tablas: lo dice igual que antes
    haces[(EQUIPO, ENERGIA)] = (7, datos_reales)
    p.calcular()
    assert p.etiqueta_motivo.text() == TABLAS_APARECIERON and sin_numero(p)
    assert p.combo_energia.currentText() == ENERGIA and p.combo_energia.isEnabled() and not p.aviso_tablas.isVisibleTo(p)
    assert [p.combo_cuna.itemData(i) for i in range(p.combo_cuna.count())] == [None, 15, 30, 45, 60]
    p.calcular()
    assert p.resultado == motor.calcular(datos_reales, pantalla.entrada_desde_textos(BASE, None, None))


def test_un_fallo_pasajero_al_listar_las_energias_no_deja_un_aviso_viejo_y_uno_que_sigue_se_dice_con_su_texto(app, fabrica, monkeypatch, datos_reales):
    """EST-2: la base ocupada un instante al abrir (aviso «No se pudieron leer…») y libre al pulsar Calcular: el aviso viejo se va. Si sigue fallando, el motivo es el fallo de ahora (no los
    dos motivos mezclados: el de la lectura que falla al abrir con energías es el de R1)."""
    servicio_falso(monkeypatch, {(EQUIPO, ENERGIA): (5, datos_reales)})
    real = um_datos_haz.energias_cargadas
    cuenta = []

    def a_veces(equipo):
        cuenta.append(1)
        if len(cuenta) in (1, 2):
            raise sqlite3.OperationalError("database is locked" if len(cuenta) == 1 else "disk I/O error")
        return real(equipo)
    monkeypatch.setattr(um_datos_haz, "energias_cargadas", a_veces)
    p = fabrica()
    assert p.aviso_tablas.text() == "No se pudieron leer las tablas guardadas del Clinac 600: database is locked"
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == "No se pudieron leer las tablas guardadas del Clinac 600: disk I/O error" == p.aviso_tablas.text() and sin_numero(p)
    p.calcular()
    assert p.etiqueta_motivo.text() == TABLAS_APARECIERON and not p.aviso_tablas.isVisibleTo(p) and p.combo_energia.currentText() == ENERGIA and sin_numero(p)
    p.calcular()
    assert p.resultado is not None


def test_si_al_volver_a_mirar_hay_energias_pero_el_haz_no_se_puede_leer_el_motivo_es_ese_fallo(app, fabrica, monkeypatch, datos_reales):
    """EST-2: los motivos no se mezclan. Sin tablas al abrir; al calcular ya hay energías pero la lectura del haz falla: el motivo es ese fallo (el mismo del aviso), no «ahora hay tablas»."""
    haces = {}
    servicio_falso(monkeypatch, haces)
    p = fabrica()
    haces[(EQUIPO, ENERGIA)] = (7, datos_reales)

    def cae(equipo, energia):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(um_datos_haz, "vigente", cae)
    escribir(p, BASE)
    p.calcular()
    assert p.etiqueta_motivo.text() == FALLO_DE_LECTURA == p.aviso_tablas.text() and p.aviso_tablas.isVisibleTo(p) and p.combo_energia.currentText() == ENERGIA and sin_numero(p)


def _sin_la_cuna(datos, angulo):
    return dataclasses.replace(datos, cunas={a: c for a, c in datos.cunas.items() if a != angulo})


def test_si_las_tablas_cambian_entre_elegir_y_calcular_la_cuna_y_su_orientacion_se_conservan(app, fabrica, monkeypatch, datos_reales):
    """EST-1 (UM4-D9): otro puesto vuelve a cargar las tablas (otro conjunto, la misma cuña de 15°). Calcular se detiene con el motivo, pero la lista conserva 15° e IN: pulsarlo otra vez no da el
    número SIN la cuña, sin avisar."""
    haces = {(EQUIPO, ENERGIA): (31, datos_reales)}
    servicio_falso(monkeypatch, haces)
    p = fabrica()
    valores = dict(BASE, ssd="90")
    escribir(p, valores, 15, "IN")
    calcular_con_enter(p)
    con_cuna = motor.calcular(datos_reales, pantalla.entrada_desde_textos(valores, 15, "IN"))
    sin_cuna = motor.calcular(datos_reales, pantalla.entrada_desde_textos(valores, None, None))
    assert p.resultado == con_cuna and abs(con_cuna.um - sin_cuna.um) > 10
    haces[(EQUIPO, ENERGIA)] = (32, datos_reales)
    calcular_con_enter(p)
    assert p.etiqueta_motivo.text() == TABLAS_CAMBIARON and sin_numero(p)
    assert (p.combo_cuna.currentData(), p.combo_orientacion.currentData()) == (15, "IN") and p.combo_orientacion.isEnabled()
    calcular_con_enter(p)
    assert p.resultado == con_cuna


def test_si_las_tablas_nuevas_ya_no_traen_la_cuna_elegida_el_motivo_lo_dice(app, fabrica, monkeypatch, datos_reales):
    """EST-1: con un conjunto nuevo sin la cuña de 15° el motivo dice que volvió a «Sin cuña» (lista y orientación vuelven a su estado inicial) y el número siguiente es sin cuña, ya avisado."""
    haces = {(EQUIPO, ENERGIA): (41, datos_reales)}
    servicio_falso(monkeypatch, haces)
    p = fabrica()
    valores = dict(BASE, ssd="90")
    escribir(p, valores, 15, "IN")
    calcular_con_enter(p)
    assert p.resultado is not None
    nuevo = _sin_la_cuna(datos_reales, 15)
    haces[(EQUIPO, ENERGIA)] = (42, nuevo)
    calcular_con_enter(p)
    assert sin_numero(p)
    assert p.etiqueta_motivo.text() == TABLAS_CAMBIARON.replace("se volvieron a leer.", "se volvieron a leer. La cuña de 15° ya no está en las tablas nuevas: volvió a Sin cuña.")
    assert [p.combo_cuna.itemData(i) for i in range(p.combo_cuna.count())] == [None, 30, 45, 60]
    assert p.combo_cuna.currentData() is None and p.combo_orientacion.currentData() is None and not p.combo_orientacion.isEnabled()
    calcular_con_enter(p)
    assert p.resultado == motor.calcular(nuevo, pantalla.entrada_desde_textos(valores, None, None))


def test_un_aviso_mas_alto_que_el_panel_se_puede_leer_entero_y_el_panel_no_se_colapsa(p):
    """TP-1: la lista de avisos desplazaba por ítem: un aviso más alto que el panel quedaba cortado SIN barra (rango 0). Y el divisor vertical podía colapsar el panel entero."""
    p.resize(1366, 700)
    p.show()
    QApplication.processEvents()
    _con_resultado(p)
    lista = p.lista_avisos
    lista.clear()
    lista.addItem(QListWidgetItem(" ".join(["Compruebe que el punto queda dentro de la abertura, a 2 [cm] o más del borde."] * 12)))
    QApplication.processEvents()
    assert lista.visualItemRect(lista.item(0)).height() > lista.viewport().height()
    assert lista.verticalScrollMode() == QAbstractItemView.ScrollPerPixel
    barra = lista.verticalScrollBar()
    assert barra.maximum() > 0
    barra.setValue(barra.maximum())
    QApplication.processEvents()
    assert lista.visualItemRect(lista.item(0)).bottom() + 1 <= lista.viewport().height() + 1          # al final se lee el final del aviso
    divisor = p.divisor_del_resultado
    divisor.setSizes([10 * divisor.height(), 0])
    QApplication.processEvents()
    assert lista.parentWidget().height() > 0 and lista.height() > 0


# Caracteres que llegan al pegar desde un PDF, un correo o un archivo de Eclipse: no se ven (formato Cf, control Cc, espacios Zs) o son un guion que no es el menos (Pd).
FRASE_NO_SE_VE = "contiene un carácter que no se ve o un guion que no es el signo menos: bórrelo y escriba el número de nuevo"
INVISIBLES = ("​", "﻿", "­", "⁠")
GUIONES = ("–", "—", "‐", "‒")
NO_SE_LIMPIAN = INVISIBLES + GUIONES + ("\x00", "\x7f")
ESPACIOS_RAROS = (" ", " ", " ", "\t")        # `str.strip` los quita al borde (como hoy); dentro del número, no se ven


def _leer_dosis(texto):
    return pantalla.leer_numero(texto, pantalla.POR_CLAVE["dosis"])


@pytest.mark.parametrize("donde", ["al final", "al principio", "dentro", "solo"])
@pytest.mark.parametrize("raro", NO_SE_LIMPIAN, ids=lambda c: f"U+{ord(c):04X}")
def test_un_caracter_que_no_se_ve_o_un_guion_largo_se_dice_y_nunca_da_un_numero(raro, donde):
    """E3: el motivo citaba «200», que se ve bien, y no decía qué sobraba."""
    texto = {"al final": f"200{raro}", "al principio": f"{raro}200", "dentro": f"2{raro}00", "solo": raro}[donde]
    with pytest.raises(motor.FaltaDato) as fallo:
        _leer_dosis(texto)
    motivo = str(fallo.value)
    assert FRASE_NO_SE_VE in motivo and "la dosis del campo en el punto [cGy]" in motivo and "Falta escribir" not in motivo
    assert not SIMBOLOS.search(motivo) and not ENTRE_PARENTESIS.search(motivo)


@pytest.mark.parametrize("campo", pantalla.CAMPOS, ids=lambda c: c.clave)
@pytest.mark.parametrize("raro", ["​", "–"], ids=["U+200B", "U+2013"])
def test_el_caracter_que_no_se_ve_se_dice_en_todos_los_campos(campo, raro):
    with pytest.raises(motor.FaltaDato) as fallo:
        pantalla.leer_numero(f"1{raro}0", campo)
    assert FRASE_NO_SE_VE in str(fallo.value) and campo.nombre in str(fallo.value)


@pytest.mark.parametrize("raro", ESPACIOS_RAROS, ids=lambda c: f"U+{ord(c):04X}")
def test_un_espacio_raro_al_borde_se_limpia_como_hoy_y_dentro_del_numero_se_dice(raro):
    assert _leer_dosis(f"{raro}200{raro}") == 200.0
    with pytest.raises(motor.FaltaDato) as fallo:
        _leer_dosis(f"2{raro}00")
    assert FRASE_NO_SE_VE in str(fallo.value)


def test_el_espacio_normal_dentro_del_numero_y_el_menos_tipografico_siguen_como_hoy():
    with pytest.raises(motor.FaltaDato) as fallo:
        _leer_dosis("2 00")
    assert FRASE_NO_SE_VE not in str(fallo.value) and "sin unidades" in str(fallo.value)
    assert _leer_dosis("−2.5") == -2.5 and _leer_dosis("-2.5") == -2.5


@pytest.mark.parametrize("equipo, energia", [("Clinac 600", "6 MV"), ("Clinac 600", "15 MV"), ("Clinac iX", "6 MV")])
def test_copiar_el_desglose_empieza_con_el_contexto_de_lo_que_se_ve(app, fabrica, monkeypatch, datos_reales, equipo, energia):
    """UM4-D11 (FID-3 y EST-5): lo copiado es lo único que queda de un cálculo (no se guarda nada) y no decía a qué haz, cuña, UM de Eclipse, error y estado correspondía. Cada dato del bloque es
    el de la pantalla."""
    servicio_falso(monkeypatch, {("Clinac 600", "6 MV"): (1, datos_reales), ("Clinac 600", "15 MV"): (2, datos_reales), ("Clinac iX", "6 MV"): (3, datos_reales)})
    p = fabrica()
    p.combo_equipo.setCurrentIndex(p.combo_equipo.findText(equipo))
    p.combo_energia.setCurrentIndex(p.combo_energia.findData(energia))
    escribir(p, dict(BASE, ssd="90", um_planeador="320.5"), 15, "OUT")
    calcular_con_enter(p)
    assert p.resultado is not None and (p.combo_equipo.currentText(), p.combo_energia.currentText()) == (equipo, energia)
    QApplication.clipboard().setText("")
    QTest.mouseClick(p.boton_copiar, Qt.LeftButton)
    primera, resto = QApplication.clipboard().text().split("\n", 1)
    assert primera == " | ".join([f"Equipo: {equipo}", f"Energía: {energia}", "Cuña: 15° (OUT)", "UM de Eclipse: 320.5 [UM]", p.etiqueta_error.text(), p.etiqueta_estado.text()])
    assert p.etiqueta_error.text().startswith("Error frente a Eclipse: ") and p.etiqueta_estado.text().startswith("Estado: ")
    assert resto == pantalla.texto_para_copiar(p.resultado)


def test_copiar_sin_um_de_eclipse_ni_cuna_no_inventa_error_ni_estado(p):
    escribir(p, BASE)
    calcular_con_enter(p)
    QTest.mouseClick(p.boton_copiar, Qt.LeftButton)
    primera, resto = QApplication.clipboard().text().split("\n", 1)
    assert primera == f"Equipo: Clinac 600 | Energía: 6 MV | Cuña: Sin cuña | {pantalla.SIN_UM_DE_ECLIPSE}"
    assert "Error frente a" not in primera and "Estado:" not in primera and " | UM de Eclipse: " not in primera
    assert resto == pantalla.texto_para_copiar(p.resultado)
