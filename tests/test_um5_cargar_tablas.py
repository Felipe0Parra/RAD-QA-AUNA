"""UM.5 (PLAN_CALCULADORA_UM_05-11.md, DC13): el botón «Cargar tablas» de la pestaña «Calculadora UM» y el historial de las tablas guardadas.

Lo que fija:
  - la CAPA PURA de `ui/paginasGuia/calculadora_um_cargar.py` sin crear widgets: el login de la sesión y el permiso (solo para pintar), leer los archivos, lo que cada uno dice de sí mismo
    (los 22 reales), los nombres cortos, de lo escrito a los argumentos del servicio o a un motivo, y los textos del resumen, del rechazo, de lo guardado y del historial;
  - el DIÁLOGO por el camino del físico, con los 22 archivos reales del 600C (`tests/datos_um/600C/`, copiados a una carpeta temporal) y una base TEMPORAL: el resumen ANTES de guardar (lo
    que se usa, lo que se ignora, lo que impide guardar y lo que conviene mirar, con los textos del servicio de UM.3); nada se guarda sin una revisión sin problemas de lo mismo que se guarda;
    un archivo cortado, de otra máquina o de otra energía, sin PDD o sin tabla abierta, o con la tabla de una cuña traspuesta no deja guardar y dice por qué, y los demás siguen en el resumen;
    un nombre desconocido avisa y deja guardar; D'0 en dmax con 1.000 escrito y su origen, o en las condiciones de la tabla; el factor escrito de cada cuña; guardar y revisar van con
    ARGUMENTOS CON NOMBRE y con el login de la sesión; los tres roles; una denegación del servicio se dice; tras guardar, la pestaña calcula con las tablas nuevas sin reiniciar y un resultado
    de antes se borra; cargar otra vez deja historial, y el historial se ve; sin hilo, el resumen de los 22 y el de un archivo de 5 [MB] salen rápido.
Trampa 2: todo cuadro modal se parcha y uno que se abriera hace caer la prueba (bajo `offscreen` colgaría la suite); el selector de archivos se parcha para devolver las rutas de cada caso.
Trampa 9: cada pantalla se cierra con la receta completa. Nunca una base de BasesDeDatos/."""
import gc
import inspect
import os
import re
import shutil
import sqlite3
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ui.paginasGuia.calculadora_um_cargar as carga      # primero: sin UM.5 la colección cae porque el módulo del diálogo no existe (el rojo)
import ui.paginasGuia.calculadora_um as pantalla
from PyQt5 import sip
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog, QLabel, QLineEdit, QMessageBox, QSizePolicy

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.user import Usuario
from services import um_datos_haz
from services import um_lector_eclipse as lector
from services import um_motor as motor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "tests", "datos_um", "600C")
EQUIPO, ENERGIA = "Clinac 600", "6 MV"
SIMBOLOS = re.compile("[✓✔✕✖✗✘⚠❌❎✅☑☒✕]")                                                                    # DA-18
ENTRE_PARENTESIS = re.compile(r"\s\((cm|mm|cGy|Gy|UM|MU|%|cGy/UM|grados|bytes|kB|MB)\)")                      # NAV-D1
OPD, OF_ABIERTA = "CLINAC 600C_Open Field - 00_Measured Depth Doses.txt", "CLINAC 600C_Open Field - 00_Output Factors.txt"
OF_15, OF_30 = "CLINAC 600C_Standard Wedge - 15_Output Factors.txt", "CLINAC 600C_Standard Wedge - 30_Output Factors.txt"

# Lo que dice cada uno de los 22 archivos reales, escrito a mano desde su nombre de Eclipse (no desde el lector): el final del nombre -> (accesorio, qué es, en la carga).
DICE = {
    "Open Field - 00_Calculated Depth Doses.txt": ("Open Field - 00", "PDD calculado por Eclipse", "Se ignora: el cálculo no lo lee"),
    "Open Field - 00_Calculated Profiles.txt": ("Open Field - 00", "perfiles calculados por Eclipse", "Se ignora: el cálculo no lo lee"),
    "Open Field - 00_Measured Depth Doses.txt": ("Open Field - 00", "PDD medido", "Se usa"),
    "Open Field - 00_Output Factors.txt": ("Open Field - 00", "tabla de factores", "Se usa"),
    "Open Field - 00_Processed Measured Profiles.txt": ("Open Field - 00", "perfiles medidos y procesados", "Se usa"),
}
for _angulo in (15, 30, 45, 60):
    DICE.update({f"Standard Wedge - {_angulo}_Measured Wedge Depth Doses.txt": (f"Standard Wedge - {_angulo}", "PDD medido con cuña", "Se usa"),
                 f"Standard Wedge - {_angulo}_Measured Wedge Profiles.txt": (f"Standard Wedge - {_angulo}", "perfiles medidos con cuña", "Se ignora: el cálculo no lo lee"),
                 f"Standard Wedge - {_angulo}_Output Factors.txt": (f"Standard Wedge - {_angulo}", "tabla de factores", "Se usa"),
                 f"Standard Wedge - {_angulo}_Wedge Transmission.txt": (f"Standard Wedge - {_angulo}", "transmisión de la cuña", "Se ignora: el cálculo no lo lee")})


def _lo_que_dice_a_mano(nombre):
    if nombre == "name.data":
        return "máquina 600C, haz 6X; Standard Wedge - 15: parámetros de la cuña (name.data)", "Se usa"
    accesorio, que, estado = DICE[nombre.replace("CLINAC 600C_", "")]
    return f"máquina 600C, haz 6X; {accesorio}: {que}", estado


# El resumen de los 22 reales (D'0 = 1.000 en dmax), copiado del que dio el servicio de UM.3 en el pre-vuelo y revisado a mano contra §8, paso 3, del plan (12 PDD, la tabla abierta, los
# perfiles con el 35 × 35 a 30 cm, las cuatro cuñas, la curva de Sc estimada, el factor de 15° deducido y los otros sin valor, los cuatro valores de H5).
AVISOS_DE_LOS_22 = [
    "Perfiles para el OAR: 40 × 40 a 1.35 [cm]; 40 × 40 a 5 [cm]; 40 × 40 a 10 [cm]; 40 × 40 a 20 [cm]; 35 × 35 a 30 [cm].",
    "Curva de Sc: estimada de la tabla de este haz y el Sp de la TG-71.",
    "D'0 = 0.8600 [cGy/UM] a 5 [cm] de profundidad, SSD 100 [cm], 10 × 10: sale de 1 [cGy/UM] en dmax con el máximo medido del PDD de 10 × 10, 100.00 [%].",
    "Tabla abierta: el valor en Y = 30 [cm], X = 25 [cm] se sale de la tendencia.",
    "Cuña de 15°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a 20 [cm] en Y.",
    "Cuña de 15°: el valor en Y = 6 [cm], X = 4 [cm] se sale de la tendencia.",
    "El factor de la cuña de 15° en 10 × 10 es 0.7701: se dedujo de su dosis de referencia, 0.6623 [cGy/UM], entre D'0, 0.8600 [cGy/UM], suponiendo que esa dosis es a 5 [cm]: "
    "falta confirmarlo.",
    "Cuña de 30°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a 20 [cm] en Y.",
    "Cuña de 30°: falta su factor en 10 × 10; hasta tenerlo se escribe por campo.",
    "Cuña de 45°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a 20 [cm] en Y.",
    "Cuña de 45°: el valor en Y = 3 [cm], X = 30 [cm] se sale de la tendencia.",
    "Cuña de 45°: el valor en Y = 15 [cm], X = 35 [cm] se sale de la tendencia.",
    "Cuña de 45°: falta su factor en 10 × 10; hasta tenerlo se escribe por campo.",
    "Cuña de 60°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a 15 [cm] en Y.",
    "Cuña de 60°: falta su factor en 10 × 10; hasta tenerlo se escribe por campo.",
    "Curva de Sc que usa el cálculo (lado [cm]: Sc): 4: 0.966, 5: 0.975, 6: 0.983, 10: 1.000, 15: 1.009, 20: 1.015, 25: 1.020, 30: 1.023, 35: 1.028, 38.0952: 1.029.",
]
USADOS = 12
FIRMA_DE_REVISAR, FIRMA_DE_GUARDAR = set(inspect.signature(um_datos_haz.revisar).parameters), set(inspect.signature(um_datos_haz.guardar).parameters)


# ================================================================================================================================== bases, pantallas y ayudas

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def dialogos(monkeypatch):
    """Trampa 2: ningún camino abre un cuadro modal. El selector de archivos de cada caso lo pone `elegir`; si se abriera sin él, la prueba cae aquí en lugar de colgar la suite."""
    def prohibido(*a, **k):
        raise AssertionError("se abrió un cuadro modal")
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(prohibido))
    for tipo in ("getOpenFileName", "getOpenFileNames", "getSaveFileName", "getExistingDirectory"):
        monkeypatch.setattr(QFileDialog, tipo, staticmethod(prohibido))
    monkeypatch.setattr(QDialog, "exec_", prohibido)
    monkeypatch.setattr(QDialog, "exec", prohibido)


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


CUENTAS = (("jefa", "Jefa de Física", "jefe"), ("admin1", "Administración", "admin"), ("fisica", "Física de Turno", "fisico"))


@pytest.fixture(scope="module")
def plantilla_vacia(tmp_path_factory):
    ruta = str(tmp_path_factory.mktemp("um5") / "vacia.db")
    _abrir_con_la_app(ruta)
    for i, (login, nombre, rol) in enumerate(CUENTAS):
        _sql(ruta, "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) VALUES (?, 'x', ?, 1, ?, 'Físico Médico', ?)", (login, nombre, 951 + i, rol))
    return ruta


@pytest.fixture(scope="module")
def originales():
    return [(nombre, open(os.path.join(DATOS, nombre), "rb").read()) for nombre in sorted(os.listdir(DATOS))]


@pytest.fixture(scope="module")
def plantilla(plantilla_vacia, originales, tmp_path_factory):
    """Una base con los 22 reales del 600C, 6 MV, ya cargados por el servicio de UM.3 (para cargar otra vez y para el historial)."""
    ruta = str(tmp_path_factory.mktemp("um5") / "cargada.db")
    shutil.copy(plantilla_vacia, ruta)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = object.__new__(Conexion)
        try:
            ok, motivo, _ = um_datos_haz.guardar(equipo=EQUIPO, energia=ENERGIA, archivos=originales, d0_dmax=1.0, d0_tabla=None, d0_origen="Eclipse: 1 cGy/UM en dmax",
                                                 wf_escritos=None, curva_sc=None, sc_origen=None, observaciones="primera carga", usuario="jefa")
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
def bd_vacia(plantilla_vacia, monkeypatch, tmp_path):
    return _usar(plantilla_vacia, monkeypatch, tmp_path)


@pytest.fixture
def bd(plantilla, monkeypatch, tmp_path):
    return _usar(plantilla, monkeypatch, tmp_path)


def cerrar(w, con_close=True):
    """Trampa 9: la receta completa (la ventana principal se suelta sin `close()`: su cierre hace un respaldo de la base, E9)."""
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

    def nueva(usuario="jefa"):
        hechas.append(pantalla.CalculadoraUM(usuario))
        return hechas[-1]
    yield nueva
    for w in hechas:
        cerrar(w)


@pytest.fixture
def reales(tmp_path):
    """Los 22 archivos reales, copiados a una carpeta temporal (así un caso puede dañar su copia): {nombre: ruta}."""
    carpeta = tmp_path / "exportados"
    carpeta.mkdir()
    for nombre in os.listdir(DATOS):
        shutil.copy(os.path.join(DATOS, nombre), carpeta / nombre)
    return {nombre: str(carpeta / nombre) for nombre in sorted(os.listdir(carpeta))}


@pytest.fixture
def elegir(monkeypatch):
    """El selector de varios archivos, parchado: devuelve las rutas que diga el caso y anota cómo se llamó."""
    llamadas = []

    def poner(rutas):
        def selector(*a, **k):
            llamadas.append(a)
            return list(rutas), carga.FILTRO_DE_ARCHIVOS
        monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(selector))
    poner.llamadas = llamadas
    return poner


def abrir(p):
    QTest.mouseClick(p.boton_cargar, Qt.LeftButton)
    d = p.dialogo_carga
    assert isinstance(d, carga.DialogoCargarTablas) and d.isVisible() and d.isModal() and d.parent() is p
    return d


def con_archivos(p, elegir, rutas):
    d = abrir(p)
    elegir(rutas)
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    return d


def filas(tabla):
    return [tuple(tabla.item(i, j).text() for j in range(tabla.columnCount())) for i in range(tabla.rowCount())]


def items(lista):
    return [lista.item(i).text() for i in range(lista.count())]


def espia(monkeypatch, nombre):
    """Envuelve `um_datos_haz.<nombre>` (el real) y anota cada llamada: (args, kwargs)."""
    real, llamadas = getattr(um_datos_haz, nombre), []

    def envuelta(*args, **kwargs):
        llamadas.append((args, kwargs))
        return real(*args, **kwargs)
    monkeypatch.setattr(um_datos_haz, nombre, envuelta)
    return llamadas


def cortar(ruta, fraccion=0.5):
    contenido = open(ruta, "rb").read()
    open(ruta, "wb").write(contenido[:int(len(contenido) * fraccion)])


def trasponer_tabla(ruta):
    """La tabla de factores con filas y columnas intercambiadas (la primera línea de datos son las X; cada fila empieza por su Y)."""
    texto = open(ruta, encoding="utf-8-sig").read()
    cabeza, _, datos = texto.partition("# Data\n")
    lineas = [linea.split(", ") for linea in datos.strip("\n").split("\n")]
    xs, filas_y = lineas[0], lineas[1:]
    ys, valores = [f[0] for f in filas_y], [f[1:] for f in filas_y]
    nuevas = [", ".join(ys)] + [", ".join([x] + [valores[i][j] for i in range(len(ys))]) for j, x in enumerate(xs)]
    open(ruta, "w", encoding="utf-8").write("\ufeff" + cabeza + "# Data\n" + "\n".join(nuevas) + "\n")


def renombrar_maquina(rutas, nueva):
    for ruta in rutas:
        texto = open(ruta, "rb").read().decode("utf-8")
        open(ruta, "wb").write(texto.replace("machine: 600C, 6X", f"machine: {nueva}, 6X").encode("utf-8"))


def escribir(p, valores, cuna=None, orientacion=None):
    """Llena el formulario de la pestaña por el teclado (los no nombrados quedan vacíos; TF, 1.000)."""
    for clave, linea in p.campos.items():
        linea.selectAll()
        QTest.keyClick(linea, Qt.Key_Delete)
        QTest.keyClicks(linea, valores.get(clave, "1.000" if clave == "tf" else ""))
    p.combo_cuna.setCurrentIndex(p.combo_cuna.findData(cuna))
    if orientacion is not None:
        p.combo_orientacion.setCurrentIndex(p.combo_orientacion.findData(orientacion))


def calcular(p, valores, cuna=None, orientacion=None):
    escribir(p, dict({"dosis": "200"}, **valores), cuna, orientacion)
    QTest.mouseClick(p.boton_calcular, Qt.LeftButton)
    return p.etiqueta_um.text()


def textos_que_se_ven(d):
    vistos = [d.windowTitle(), d.estado.text(), d.etiqueta_vigente.text(), d.etiqueta_conteo.text(), d.titulo_problemas.text(), d.titulo_avisos.text()]
    vistos += [w.text() for w in d.findChildren(QLabel)] + [w.toolTip() for w in d.findChildren(QLineEdit)] + [w.placeholderText() for w in d.findChildren(QLineEdit)]
    vistos += items(d.lista_problemas) + items(d.lista_avisos) + [c for fila in filas(d.tabla_archivos) for c in fila]
    return vistos


# ================================================================================================================================== capa pura

# Los textos y medidas fijos del diálogo, escritos aquí tal cual (lo que ve el físico no cambia sin que una prueba lo diga).
TEXTOS_FIJOS = {
    'TITULO_DE_LA_CARGA': 'Cargar las tablas de una energía',
    'TITULO_DEL_HISTORIAL': 'Historial de las tablas guardadas',
    'TAMANO_DE_LA_CARGA': (1280, 700),
    'TAMANO_DEL_HISTORIAL': (1100, 560),
    'ALTO_DE_UNA_FILA': 24,
    'ANCHOS_DE_LOS_ARCHIVOS': (380, 520),
    'ANCHOS_DEL_HISTORIAL': (150, 140, 115, 330, 90, 280),
    'ANCHOS_DE_LOS_GUARDADOS': (150, 200, 360, 120, 160),
    'ANCHO_DEL_CONTEO': 320,
    'FILTRO_DE_ARCHIVOS': 'Archivos de Eclipse (*.txt *.data *.asc);;Todos los archivos (*)',
    'TAMANO_MAXIMO_BYTES': 20971520,
    'D0_EN_DMAX': 'en dmax',
    'D0_EN_LA_TABLA': 'en las condiciones de la tabla',
    'ORIGEN_INICIAL': 'Eclipse: 1 cGy/UM en dmax',
    'AYUDA_DE_CARGAR': 'Elija los archivos que exporta Eclipse para una energía: antes de guardar se ve qué entendió la app, y nada se guarda sin pulsar «Guardar estas tablas».',
    'AYUDA_SIN_PERMISO': 'Las tablas las cargan el físico jefe o el administrador. Con esta cuenta se pueden ver las tablas cargadas y su historial, pero no cargarlas.',
    'AYUDA_DEL_HISTORIAL': 'Las cargas del equipo y la energía elegidos: la vigente y las que reemplazó, con quién y cuándo las cargó.',
    'SIN_ARCHIVOS': 'Pulse «Elegir archivos» y elija todos los que exporta Eclipse para una energía (los que el cálculo no lee se ignoran).',
    'LO_ESCRITO_CAMBIO': 'Lo escrito o los archivos cambiaron desde la última revisión: pulse «Revisar» para ver el resumen de nuevo antes de guardar.',
    'SE_PUEDE_GUARDAR': 'Nada impide guardar. Revise el resumen y, si es lo que quiere, pulse «Guardar estas tablas».',
    'NADA_IMPIDE': 'Nada impide guardar.',
    'SIN_REVISAR': 'Sin revisar: corrija lo escrito',
    'FILAS_Y_COLUMNAS': 'Filas y columnas: en las tablas de factores de Eclipse las filas son Y y las columnas X. En cada cuña el lado corto de su tabla es el del gradiente y, si está su name.data, su orientación debe decir lo mismo; si no lo dice, no se puede guardar.',
    'COLUMNAS_DE_LOS_ARCHIVOS': ('Archivo', 'Lo que dice ser', 'En la carga'),
    'COLUMNAS_DEL_HISTORIAL': ('Cargadas el', 'Por', 'Estado', "D'0", 'Archivos', 'Reemplazó a', 'Observaciones'),
    'COLUMNAS_DE_LOS_GUARDADOS': ('Accesorio', 'Dato', 'Archivo', 'Huella', 'Tamaño [bytes]', 'Estado'),
    'QUE_ES': {'OPD': 'PDD medido', 'OPD_calculated': 'PDD calculado por Eclipse', 'OPP_processed': 'perfiles medidos y procesados', 'OPP_calculated': 'perfiles calculados por Eclipse', 'OutputFactorTable': 'tabla de factores', 'WDD': 'PDD medido con cuña', 'WDP': 'perfiles medidos con cuña', 'WedgeTransmission': 'transmisión de la cuña', 'WedgeParameters': 'parámetros de la cuña (name.data)'},
}
CAMPO_D0_ESPERADO = ('d0', "D'0 [cGy/UM]", "D'0 [cGy/UM]", True, None, '1.000', '', 'La tasa de referencia de Eclipse: 1 [cGy/UM] en dmax. Si la tabla de factores no está a la SSD de los PDD, se escribe en las condiciones de la tabla.')


def test_los_textos_y_las_medidas_fijas_son_los_que_ve_el_fisico():
    for nombre, valor in TEXTOS_FIJOS.items():
        assert getattr(carga, nombre) == valor, nombre
    d = carga.CAMPO_D0
    assert (d.clave, d.etiqueta, d.nombre, d.obligatorio, d.omision, d.inicial, d.ayuda, d.explicacion) == CAMPO_D0_ESPERADO
    assert carga.campo_de_la_cuna(15) == pantalla.Campo("wf_15", "Factor de la cuña de 15° en 10 × 10", "el factor de la cuña de 15° en 10 × 10", False, ayuda="opcional",
                                                     explicacion="Opcional. El factor de la cuña de 15° en 10 × 10 a la profundidad de la tabla. Vacío, se deduce de su name.data si está; "
                                                                 "si no, se escribe por campo.")


def test_el_login_de_la_sesion_es_el_de_su_objeto_o_el_texto():
    assert carga.login_de_la_sesion(Usuario(username="jefa", fullname="Jefa de Física")) == "jefa"
    assert carga.login_de_la_sesion(Usuario(username="  admin1 ")) == "admin1"
    assert carga.login_de_la_sesion("fisica") == "fisica"
    for nada in (None, "", "   ", Usuario(), 7, object()):
        assert carga.login_de_la_sesion(nada) is None


@pytest.mark.parametrize("login, puede", [("jefa", True), ("admin1", True), ("fisica", False), ("nadie", False), (None, False), ("", False)])
def test_quien_puede_cargar_es_la_regla_del_servicio(bd_vacia, login, puede):
    """PC-12 de UM.3: el jefe y el administrador; el rol «físico» no (DA-35 no alcanza a `es_fisico_jefe`)."""
    assert carga.puede_cargar(login) is puede
    if login:
        from services.permisos import es_fisico_jefe
        assert es_fisico_jefe(login) is puede


def test_los_nombres_cortos_distinguen_solo_lo_que_hace_falta():
    rutas = ["/a/exportados/15/name.data", "/a/exportados/30/name.data", "/a/exportados/OPD.txt", "C:\\Eclipse\\600C\\OF.txt", "/x/y/a/b.txt", "/x/z/a/b.txt"]
    assert carga.nombres_para_mostrar(rutas) == {"/a/exportados/15/name.data": "15/name.data", "/a/exportados/30/name.data": "30/name.data", "/a/exportados/OPD.txt": "OPD.txt",
                                                 "C:\\Eclipse\\600C\\OF.txt": "OF.txt", "/x/y/a/b.txt": "y/a/b.txt", "/x/z/a/b.txt": "z/a/b.txt"}
    assert carga.nombres_para_mostrar([]) == {}


def test_legible_cambia_cada_ruta_por_su_nombre_corto_empezando_por_la_mas_larga():
    cortos = carga.nombres_para_mostrar(["/d/OF.txt", "/d/OF.txt.viejo"])
    assert carga.legible("/d/OF.txt.viejo: cortado; /d/OF.txt dice máquina X", cortos) == "OF.txt.viejo: cortado; OF.txt dice máquina X"
    assert carga.legible("sin rutas", cortos) == "sin rutas"
    anidadas = carga.nombres_para_mostrar(["/d/a.txt", "/e/d/a.txt"])          # el nombre corto de una contiene la otra ruta: no se vuelve a cambiar
    assert anidadas == {"/d/a.txt": "d/a.txt", "/e/d/a.txt": "e/d/a.txt"}
    assert carga.legible("/e/d/a.txt: cortado; /d/a.txt: bien", anidadas) == "e/d/a.txt: cortado; d/a.txt: bien"
    prefijo = {"/d/a": "a", "/d/a/b.txt": "b.txt"}                               # una ruta que empieza como otra se cambia entera (la más larga primero)
    assert carga.legible("/d/a/b.txt: x", prefijo) == "b.txt: x" and carga.legible("/d/a: y", prefijo) == "a: y" and carga.legible("z", {}) == "z"


@pytest.mark.parametrize("nombre", sorted(os.listdir(DATOS)))
def test_lo_que_dice_cada_uno_de_los_22_reales(originales, nombre):
    identidad, texto = carga.lo_que_dice(dict(originales)[nombre])
    assert texto == _lo_que_dice_a_mano(nombre)[0]
    assert identidad == lector.identidad(lector.decodificar(dict(originales)[nombre]))


@pytest.mark.parametrize("contenido, motivo", [(b"hola", "la cabecera no dice máquina, accesorio y tipo de dato"), ("x".encode("utf-16"), "bytes nulos"), (b"", "la cabecera no dice")])
def test_lo_que_no_se_entiende_dice_por_que(contenido, motivo):
    identidad, texto = carga.lo_que_dice(contenido)
    assert identidad is None and texto.startswith("No se entiende su cabecera: ") and motivo in texto


def test_las_cunas_y_la_energia_que_dicen_los_archivos(originales):
    identidades = [carga.lo_que_dice(c)[0] for _, c in originales]
    assert carga.cunas_de(identidades) == [15, 30, 45, 60] and carga.cunas_de(identidades[:5]) == []
    assert carga.energia_de(identidades) == "6 MV" and carga.cunas_de(identidades + [None]) == [15, 30, 45, 60]
    otra = lector.Identidad("600C", "10X", "Open Field - 00", "OPD")
    rara = lector.Identidad("600C", "6", "Open Field - 00", "OPD")
    assert carga.energia_de(identidades + [otra]) is None and carga.energia_de([rara]) is None and carga.energia_de([]) is None and carga.energia_de([None]) is None


def test_leer_archivos_dice_lo_que_no_se_lee(tmp_path, monkeypatch):
    bueno, grande = tmp_path / "bueno.txt", tmp_path / "grande.txt"
    bueno.write_bytes(b"abc")
    grande.write_bytes(b"x")
    real = os.path.getsize
    monkeypatch.setattr(carga.os.path, "getsize", lambda r: carga.TAMANO_MAXIMO_BYTES + 1 if r == str(grande) else real(r))
    leidos, no = carga.leer_archivos([str(bueno), str(tmp_path / "no_esta.txt"), str(grande)])
    assert leidos == [(str(bueno), b"abc")]
    assert no == [(str(tmp_path / "no_esta.txt"), "no se pudo leer (No such file or directory)"),
                  (str(grande), "mide más de 20 [MB]: no es un archivo de los que exporta Eclipse y no se lee")]


ARCHIVOS = [("/d/a.txt", b"x")]


def _textos(**cambios):
    base = {"equipo": EQUIPO, "energia": "6 MV", "d0": "1.000", "donde": carga.D0_EN_DMAX, "origen": carga.ORIGEN_INICIAL, "wf": {}, "observaciones": "", "archivos": ARCHIVOS}
    base.update(cambios)
    return base


def test_de_lo_escrito_a_los_argumentos_del_servicio():
    assert carga.carga_desde_textos(**_textos()) == {"equipo": EQUIPO, "energia": "6 MV", "archivos": ARCHIVOS, "d0_dmax": 1.0, "d0_tabla": None, "d0_origen": carga.ORIGEN_INICIAL,
                                                     "wf_escritos": {}, "curva_sc": None, "sc_origen": None, "observaciones": None}
    k = carga.carga_desde_textos(**_textos(energia=" 6x ", d0="0,86", donde=carga.D0_EN_LA_TABLA, origen="  medido ", wf={15: "", 30: "0,61", 45: " "}, observaciones=" nota "))
    assert (k["energia"], k["d0_dmax"], k["d0_tabla"], k["d0_origen"], k["wf_escritos"], k["observaciones"]) == ("6 MV", None, 0.86, "medido", {30: 0.61}, "nota")
    # los argumentos son EXACTAMENTE los de `revisar` y, con el usuario, los de `guardar`
    assert set(k) == FIRMA_DE_REVISAR == FIRMA_DE_GUARDAR - {"usuario"}


def test_un_cero_escrito_no_es_un_campo_vacio():
    k = carga.carga_desde_textos(**_textos(d0="0", wf={15: "0"}))
    assert k["d0_dmax"] == 0.0 and k["wf_escritos"] == {15: 0.0}        # los rangos los dice el servicio: nada se cae al valor por omisión


@pytest.mark.parametrize("cambios, motivos", [
    ({"d0": ""}, ["Falta escribir D'0 [cGy/UM]."]),
    ({"d0": "1 cGy"}, ["No se entiende D'0 [cGy/UM]: «1 cGy». Escriba solo el número, con punto o coma decimal y sin unidades."]),
    ({"energia": ""}, ["Falta escribir la energía, por ejemplo «6 MV»."]),
    ({"energia": "6"}, ["No se entiende la energía «6»: se escribe como «6 MV» o «6X» (solo fotones)."]),
    ({"energia": "6 MeV"}, ["No se entiende la energía «6 MeV»: se escribe como «6 MV» o «6X» (solo fotones)."]),
    ({"origen": "  "}, ["Falta escribir de dónde sale D'0, por ejemplo «Eclipse: 1 cGy/UM en dmax»."]),
    ({"wf": {30: "0.6x"}}, ["No se entiende el factor de la cuña de 30° en 10 × 10: «0.6x». Escriba solo el número, con punto o coma decimal y sin unidades."]),
    ({"energia": "", "d0": "x", "wf": {45: "1e0", 15: "y"}, "origen": ""},
     ["Falta escribir la energía, por ejemplo «6 MV».", "No se entiende D'0 [cGy/UM]: «x». Escriba solo el número, con punto o coma decimal y sin unidades.",
      "No se entiende el factor de la cuña de 15° en 10 × 10: «y». Escriba solo el número, con punto o coma decimal y sin unidades.",
      "No se entiende el factor de la cuña de 45° en 10 × 10: «1e0». Escriba solo el número, con punto o coma decimal y sin unidades.",
      "Falta escribir de dónde sale D'0, por ejemplo «Eclipse: 1 cGy/UM en dmax»."]),
])
def test_lo_escrito_que_no_se_entiende_da_todos_sus_motivos_en_orden(cambios, motivos):
    with pytest.raises(motor.FaltaDato) as fallo:
        carga.carga_desde_textos(**_textos(**cambios))
    assert str(fallo.value).split("\n") == motivos


def test_las_filas_de_los_archivos_y_el_conteo():
    from services.um_armar import Revision
    archivos = [("/d/a", b""), ("/d/b", b""), ("/d/c", b""), ("/d/e", b""), ("/d/g", b""), ("/d/g.txt", b"")]
    dichos = {r: f"dice {r}" for r, _ in archivos}
    cortos = carga.nombres_para_mostrar([r for r, _ in archivos] + ["/d/f"])
    revision = Revision(("/d/a", "/d/g", "/d/g.txt"), ("/d/b",), ("/d/c: cortado", "/d/g.txt dice máquina X, y se está cargando para Clinac 600."), ())
    assert carga.filas_de_los_archivos(archivos, [("/d/f", "no se pudo leer (x)")], dichos, revision, cortos) == [
        ("a", "dice /d/a", "Se usa"), ("b", "dice /d/b", "Se ignora: el cálculo no lo lee"), ("c", "dice /d/c", "Impide guardar: vea el motivo"),
        ("e", "dice /d/e", "Sin revisar: lo impide otro problema"), ("g", "dice /d/g", "Se usa"),                     # «/d/g» no es «/d/g.txt»
        ("g.txt", "dice /d/g.txt", "Impide guardar: vea el motivo"),                                                  # se usaría, pero es de otra máquina: no «se usa»
        ("f", "no se pudo leer (x)", "Impide guardar: no se leyó")]
    assert [f[2] for f in carga.filas_de_los_archivos(archivos, [], dichos, None, cortos)] == [carga.SIN_REVISAR] * 6
    assert carga.texto_del_conteo(archivos[:4], [("/d/f", "")], revision) == "5 archivos: 1 se usa, 1 se ignora y 2 impiden guardar; 1 no se pudo leer."      # UM5-S8 (clase b): el nombrado en un problema y el que el servicio no clasificó impiden guardar y suman el total
    assert carga.texto_del_conteo(archivos[:1], [], Revision(("/d/a",), (), (), ())) == "1 archivo: 1 se usa y 0 se ignoran."
    assert carga.texto_del_conteo([], [("/d/f", ""), ("/d/g", "")], Revision((), (), (), ())) == "2 archivos: 0 se usan y 0 se ignoran; 2 no se pudieron leer."
    assert carga.texto_del_conteo(archivos, [], Revision((), (), ("/d/a: bytes nulos",), ())) == "6 archivos: sin revisar."     # el servicio cortó la revisión
    assert carga.texto_del_conteo(archivos, [], None) == "6 archivos: sin revisar." and carga.texto_del_conteo(archivos[:1], [("/d/f", "")], None) == "2 archivos: sin revisar; 1 no se pudo leer."


def test_los_textos_de_lo_vigente_del_rechazo_y_de_lo_guardado():
    assert carga.texto_de_lo_vigente(EQUIPO, ENERGIA, None) == "No hay tablas guardadas del Clinac 600, 6 MV: estas serán las primeras."
    assert carga.texto_de_lo_vigente(EQUIPO, ENERGIA, {"fecha_registro": "2026-11-10 11:00:00", "usuario": "Jefa de Física"}) == (
        "Ya hay tablas vigentes del Clinac 600, 6 MV, cargadas el 2026-11-10 11:00:00 por Jefa de Física: al guardar, estas pasan a ser las vigentes y aquellas quedan en el historial.")
    cortos = {"/d/OPD.txt": "OPD.txt"}
    assert carga.texto_del_rechazo(um_datos_haz.DENEGADO, cortos) == "No se guardó nada: solo el físico jefe o el administrador pueden cargar las tablas de un acelerador"
    assert carga.texto_del_rechazo(um_datos_haz.USUARIO_INVALIDO, cortos) == "No se guardó nada: falta el usuario que carga las tablas, o no es un texto"
    assert carga.texto_del_rechazo(um_datos_haz.NO_SE_GUARDA + "/d/OPD.txt: parece cortado", cortos) == "No se guardó nada: OPD.txt: parece cortado"
    assert carga.texto_de_lo_guardado(EQUIPO, ENERGIA, True) == "Guardadas las tablas del Clinac 600, 6 MV: la pestaña ya calcula con ellas. Las anteriores quedan en el historial."
    assert carga.texto_de_lo_guardado(EQUIPO, ENERGIA, False).endswith("Son las primeras de esta energía.")


def test_las_filas_del_historial_dicen_quien_cuando_y_que_reemplazo():
    archivo = {"accesorio": "Open Field - 00", "dato": "OPD", "nombre_archivo": "C:\\Eclipse\\OPD.txt", "sha256": "ab" * 32, "bytes": 1234, "activo": 0}
    registros = [
        {"fecha_registro": "2026-11-10 12:00:00", "usuario": "Jefa de Física", "activo": 1, "d0_dmax": 1.0, "d0_tabla": None, "d0_origen": "Eclipse", "archivos": [dict(archivo, activo=1)] * 2,
         "observaciones": None, "problema": None},
        {"fecha_registro": "2026-11-09 08:00:00", "usuario": "Administración", "activo": 0, "d0_dmax": None, "d0_tabla": 0.86, "d0_origen": "medido", "archivos": [archivo],
         "observaciones": "la primera", "problema": None},
        {"fecha_registro": "2026-11-08 08:00:00", "usuario": "Jefa de Física", "activo": 0, "d0_dmax": 1.0, "d0_tabla": None, "d0_origen": "x", "archivos": [],
         "observaciones": "", "problema": "sus factores de cuña o su curva de Sc están dañados"},
    ]
    assert carga.filas_del_historial(registros) == [
        ("2026-11-10 12:00:00", "Jefa de Física", "Vigente", "1 [cGy/UM] en dmax (Eclipse)", "2", "La carga del 2026-11-09 08:00:00, de Administración", ""),
        ("2026-11-09 08:00:00", "Administración", "Reemplazada", "0.86 [cGy/UM] en las condiciones de la tabla (medido)", "1", "La carga del 2026-11-08 08:00:00, de Jefa de Física",
         "la primera"),
        ("2026-11-08 08:00:00", "Jefa de Física", "Reemplazada", "No se puede leer: sus factores de cuña o su curva de Sc están dañados", "0", "Ninguna: fue la primera", "")]
    assert carga.filas_de_los_archivos_guardados(registros[1]) == [("Open Field - 00", "PDD medido", "OPD.txt", "abababababab", "1234", "Anulado")]
    assert carga.filas_de_los_archivos_guardados(registros[0])[0][5] == "Vigente" and carga.filas_del_historial([]) == []
    assert carga.filas_de_los_archivos_guardados({"archivos": [dict(archivo, activo=None)]})[0][5] == "Vigente"            # activo vacío es vigente (`filtro_activo`)
    assert carga.filas_del_historial([dict(registros[0], activo=None)])[0][2] == "Vigente"


# ================================================================================================================================== el botón y los tres roles

@pytest.mark.parametrize("login, puede", [("jefa", True), ("admin1", True), ("fisica", False)])
def test_el_boton_se_habilita_solo_para_quien_puede_y_a_los_demas_les_dice_quien_carga(bd_vacia, fabrica, login, puede):
    p = fabrica(Usuario(username=login))
    assert p.login == login and p.boton_cargar.isEnabled() is puede
    assert p.boton_cargar.toolTip() == (carga.AYUDA_DE_CARGAR if puede else carga.AYUDA_SIN_PERMISO)
    assert p.boton_historial.isEnabled() and p.boton_historial.toolTip() == carga.AYUDA_DEL_HISTORIAL
    assert p.aviso_tablas.text() == pantalla.texto_sin_tablas(EQUIPO) and "el físico jefe o el administrador" in p.aviso_tablas.text()
    if not puede:
        assert "el físico jefe o el administrador" in p.boton_cargar.toolTip()
        QTest.mouseClick(p.boton_cargar, Qt.LeftButton)
        assert p.dialogo_carga is None           # un botón apagado no abre nada


def test_sin_sesion_reconocida_no_se_carga(bd_vacia, fabrica):
    for usuario in (None, Usuario(), "nadie"):
        p = fabrica(usuario)
        assert not p.boton_cargar.isEnabled() and p.boton_cargar.toolTip() == carga.AYUDA_SIN_PERMISO


def test_el_historial_va_debajo_de_cargar_tablas_y_la_ventana_no_se_ensancha(bd_vacia, app, monkeypatch):
    """Los dos botones, uno sobre otro, en la fila de arriba (caben en el alto de la ecuación): lado a lado, el mínimo de la ventana principal real pasaba de 1194 a 1280 [px]."""
    from ui.mainpages import MainWindow
    Conexion._instance = None
    conexion = Conexion()
    w = MainWindow(Usuario(username="jefa", fullname="Jefa de Física"))
    try:
        indice = [w.tabs.tabText(i) for i in range(w.tabs.count())].index("Calculadora UM")
        w._cargar_pestania_diferida(indice)
        p = w._tab_instancias[indice]
        barra = p.layout().itemAt(0).layout()
        pila = next(barra.itemAt(i).layout() for i in range(barra.count()) if barra.itemAt(i).layout() is not None)
        assert [pila.itemAt(i).widget() for i in range(pila.count())] == [p.boton_cargar, p.boton_historial] and p.boton_historial.text() == "Historial"
        con_el_boton = w.minimumSizeHint().width()
        p.boton_historial.hide()
        QApplication.processEvents()
        assert w.minimumSizeHint().width() == con_el_boton         # el botón no ensancha la ventana: el mínimo es el mismo con él y sin él
        p.boton_historial.show()
    finally:
        cerrar(w, con_close=False)
        conexion.con.close()
        Conexion._instance = None


# ================================================================================================================================== el resumen de los 22 reales y el guardado

def test_los_22_reales_dan_el_resumen_esperado_antes_de_guardar(bd_vacia, fabrica, elegir, reales):
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    assert len(elegir.llamadas) == 1 and elegir.llamadas[0][1] == "Elija los archivos de una energía" and elegir.llamadas[0][3] == carga.FILTRO_DE_ARCHIVOS
    assert filas(d.tabla_archivos) == [(nombre,) + _lo_que_dice_a_mano(nombre) for nombre in reales]
    assert [f[2] for f in filas(d.tabla_archivos)].count("Se usa") == USADOS
    assert d.etiqueta_conteo.text() == "22 archivos: 12 se usan y 10 se ignoran."
    assert items(d.lista_problemas) == [carga.NADA_IMPIDE] and d.titulo_problemas.text() == "Lo que impide guardar (0)"
    assert items(d.lista_avisos) == AVISOS_DE_LOS_22 and d.titulo_avisos.text() == f"Lo que entendió la app y conviene mirar ({len(AVISOS_DE_LOS_22)})"
    assert d.etiqueta_vigente.text() == "No hay tablas guardadas del Clinac 600, 6 MV: estas serán las primeras."
    assert d.linea_energia.text() == ENERGIA                 # la pestaña no tenía energía: se tomó de lo que dicen los archivos
    assert d.linea_d0.text() == "1.000" and d.combo_d0.currentText() == carga.D0_EN_DMAX and d.linea_origen.text() == carga.ORIGEN_INICIAL
    assert sorted(d.campos_wf) == [15, 30, 45, 60] and all(linea.text() == "" for linea in d.campos_wf.values())
    assert d.nota_filas_y_columnas.text() == carga.FILAS_Y_COLUMNAS and "las filas son Y y las columnas X" in carga.FILAS_Y_COLUMNAS
    assert d.titulo_cunas.isVisibleTo(d)
    assert d.boton_guardar.isEnabled() and d.estado.text() == carga.SE_PUEDE_GUARDAR
    assert _sql(bd_vacia, "SELECT COUNT(*) FROM um_datos_haz") == [(0,)]          # revisar no guarda nada
    assert QApplication.overrideCursor() is None


def test_guardar_deja_las_tablas_y_la_pestana_calcula_con_ellas_sin_reiniciar(bd_vacia, fabrica, elegir, reales):
    p = fabrica()
    assert p.combo_energia.count() == 0 and p.aviso_tablas.isVisibleTo(p)
    d = con_archivos(p, elegir, list(reales.values()))
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert d.estado.text() == "Guardadas las tablas del Clinac 600, 6 MV: la pestaña ya calcula con ellas. Son las primeras de esta energía."
    assert not d.boton_guardar.isEnabled()                    # lo guardado no se vuelve a guardar sin revisar otra vez
    assert d.etiqueta_vigente.text() == ""                    # «No hay tablas guardadas...» ya no es cierto
    assert _sql(bd_vacia, "SELECT equipo, energia, d0_dmax, d0_tabla, d0_origen, wf_escritos, curva_sc, sc_origen, observaciones, usuario FROM um_datos_haz WHERE activo = 1") == [
        (EQUIPO, ENERGIA, 1.0, None, carga.ORIGEN_INICIAL, "{}", None, None, None, "Jefa de Física")]
    assert _sql(bd_vacia, "SELECT COUNT(*), COUNT(DISTINCT nombre_archivo) FROM um_archivo_haz WHERE activo = 1") == [(USADOS, USADOS)]
    assert [p.combo_energia.itemText(i) for i in range(p.combo_energia.count())] == [ENERGIA] and p.combo_energia.isEnabled() and not p.aviso_tablas.isVisibleTo(p)
    assert [p.combo_cuna.itemData(i) for i in range(p.combo_cuna.count())] == [None, 15, 30, 45, 60]
    # las UM de la pestaña (UM.4, logs/UM2/h_datos_reales_UM2.txt) con las tablas que acaba de cargar el diálogo
    assert calcular(p, {"x": "10", "y": "10", "ssd": "100", "prof": "10"}) == "UM calculadas: 302.1 [UM]"
    assert calcular(p, {"x": "15", "y": "15", "x_ef": "10", "y_ef": "10", "ssd": "90", "prof": "10"}) == "UM calculadas: 250.5 [UM]"
    assert calcular(p, {"x": "10", "y": "10", "ssd": "90", "prof": "10"}, 15, "IN") == "UM calculadas: 326.8 [UM]"


def test_guardar_y_revisar_van_con_argumentos_con_nombre_y_con_el_login_de_la_sesion(bd_vacia, app, elegir, reales, monkeypatch):
    """La llamada se fija: `guardar` tiene 11 parámetros y las dos llamadas de UM.4 los ponían en posiciones distintas. El usuario es el login de la sesión, el `_usuario` del objeto que la
    ventana principal le pasa a la pestaña (`CalculadoraUM(self.user_id)`)."""
    from ui.mainpages import MainWindow
    revisiones, guardados = espia(monkeypatch, "revisar"), espia(monkeypatch, "guardar")
    Conexion._instance = None
    conexion = Conexion()
    w = MainWindow(Usuario(username="jefa", fullname="Jefa de Física"))
    try:
        indice = [w.tabs.tabText(i) for i in range(w.tabs.count())].index("Calculadora UM")
        w._cargar_pestania_diferida(indice)
        p = w._tab_instancias[indice]
        assert p.usuario is w.user_id and p.login == "jefa"
        d = con_archivos(p, elegir, list(reales.values()))
        QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
        (args_r, kw_r), = revisiones
        (args_g, kw_g), = guardados
        assert args_r == () and set(kw_r) == FIRMA_DE_REVISAR and len(FIRMA_DE_REVISAR) == 10
        assert args_g == () and set(kw_g) == FIRMA_DE_GUARDAR and len(FIRMA_DE_GUARDAR) == 11 and kw_g["usuario"] == "jefa"
        assert {k: v for k, v in kw_g.items() if k != "usuario"} == kw_r          # se guarda EXACTAMENTE lo revisado
        assert kw_g["archivos"] == [(ruta, open(ruta, "rb").read()) for ruta in reales.values()]
        assert _sql(conection_mod.ruta_base_datos(), "SELECT usuario FROM um_datos_haz") == [("Jefa de Física",)]
        assert p.combo_energia.currentText() == ENERGIA
    finally:
        cerrar(w, con_close=False)
        conexion.con.close()
        Conexion._instance = None


def test_se_guarda_lo_revisado_aunque_el_campo_cambie_sin_pasar_por_el_teclado(bd_vacia, fabrica, elegir, reales):
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    d.linea_d0.setText("1.2")                   # sin `textEdited`: «Guardar» sigue con lo revisado, no con el campo
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert _sql(bd_vacia, "SELECT d0_dmax FROM um_datos_haz") == [(1.0,)]


@pytest.mark.parametrize("cambio", ["equipo", "energia", "d0", "donde", "origen", "observaciones", "wf"])
def test_cualquier_cambio_apaga_guardar_hasta_revisar_otra_vez(bd_vacia, fabrica, elegir, reales, cambio):
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    assert d.boton_guardar.isEnabled()
    if cambio == "equipo":
        d.combo_equipo.setCurrentIndex(1)
    elif cambio == "donde":
        d.combo_d0.setCurrentIndex(1)
    else:
        linea = {"energia": d.linea_energia, "d0": d.linea_d0, "origen": d.linea_origen, "observaciones": d.linea_observaciones, "wf": d.campos_wf[30]}[cambio]
        QTest.keyClicks(linea, "1" if cambio in ("d0", "wf") else " x")
    assert not d.boton_guardar.isEnabled() and d.estado.text() == carga.LO_ESCRITO_CAMBIO and d._revisada is None
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert _sql(bd_vacia, "SELECT COUNT(*) FROM um_datos_haz") == [(0,)]
    QTest.mouseClick(d.boton_revisar, Qt.LeftButton)
    assert d.estado.text() != carga.LO_ESCRITO_CAMBIO


def test_cargar_otra_vez_reemplaza_deja_historial_y_borra_el_resultado(bd, fabrica, elegir, reales):
    p = fabrica()
    assert calcular(p, {"x": "10", "y": "10", "ssd": "100", "prof": "10"}) == "UM calculadas: 302.1 [UM]" and p.resultado is not None
    (primero,), = _sql(bd, "SELECT id FROM um_datos_haz")
    d = con_archivos(p, elegir, list(reales.values()))
    QTest.keyClicks(d.linea_observaciones, "segunda carga")
    QTest.mouseClick(d.boton_revisar, Qt.LeftButton)
    assert re.fullmatch(r"Ya hay tablas vigentes del Clinac 600, 6 MV, cargadas el \d{4}-\d\d-\d\d \d\d:\d\d:\d\d por Jefa de Física: al guardar, estas pasan a ser las vigentes y "
                        r"aquellas quedan en el historial\.", d.etiqueta_vigente.text())
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert d.estado.text().endswith("Las anteriores quedan en el historial.")
    assert p.resultado is None and p.etiqueta_um.text() == pantalla.SIN_RESULTADO        # nunca un número de otro conjunto (UM4-D6, UM4-D9)
    (segundo,), = _sql(bd, "SELECT id FROM um_datos_haz WHERE activo = 1")
    assert segundo != primero and set(p._haces) <= {segundo}
    assert _sql(bd, "SELECT activo, observaciones FROM um_datos_haz ORDER BY id") == [(0, "primera carga"), (1, "segunda carga")]
    assert _sql(bd, "SELECT accion FROM audit_log WHERE tabla = 'um_datos_haz' ORDER BY id") == [("guardar",), ("reemplazo",)]
    assert calcular(p, {"x": "10", "y": "10", "ssd": "100", "prof": "10"}) == "UM calculadas: 302.1 [UM]"
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    h = p.dialogo_historial
    assert isinstance(h, carga.DialogoHistorial) and h.isVisible() and not h.isModal() and h.parent() is p
    assert h.aviso.text() == "2 cargas del Clinac 600, 6 MV, de la más reciente a la más antigua."
    vistas = filas(h.tabla)
    assert [f[1:5] for f in vistas] == [("Jefa de Física", "Vigente", "1 [cGy/UM] en dmax (Eclipse: 1 cGy/UM en dmax)", "12"),
                                         ("Jefa de Física", "Reemplazada", "1 [cGy/UM] en dmax (Eclipse: 1 cGy/UM en dmax)", "12")]
    assert vistas[0][5] == f"La carga del {vistas[1][0]}, de Jefa de Física" and vistas[1][5] == "Ninguna: fue la primera"
    assert [f[6] for f in vistas] == ["segunda carga", "primera carga"]
    assert len(filas(h.tabla_archivos)) == USADOS and {f[5] for f in filas(h.tabla_archivos)} == {"Vigente"}
    h.tabla.setCurrentCell(1, 0)
    assert {f[5] for f in filas(h.tabla_archivos)} == {"Anulado"} and filas(h.tabla_archivos)[0][:3] == ("Open Field - 00", "PDD medido", OPD)


def test_tras_guardar_la_pestana_queda_en_el_equipo_y_la_energia_de_la_carga(bd_vacia, fabrica, elegir, reales):
    p = fabrica()
    p.combo_equipo.setCurrentIndex(p.combo_equipo.findText("Clinac iX"))
    d = con_archivos(p, elegir, list(reales.values()))
    assert d.combo_equipo.currentText() == "Clinac iX" and d.estado.text().startswith("No se puede guardar")
    d.combo_equipo.setCurrentIndex(d.combo_equipo.findText(EQUIPO))
    QTest.mouseClick(d.boton_revisar, Qt.LeftButton)
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert p.combo_equipo.currentText() == EQUIPO and p.combo_energia.currentText() == ENERGIA and not p.aviso_tablas.isVisibleTo(p)


def test_tras_guardar_otra_energia_la_pestana_la_elige_y_conserva_la_anterior(bd, fabrica, elegir, reales):
    """Con 6 MV ya cargada, una carga de 10 MV (los mismos archivos con la cabecera del haz cambiada) queda elegida en la pestaña, después de la de 6 MV, y la de 6 MV sigue igual."""
    for ruta in reales.values():
        texto = open(ruta, "rb").read().decode("utf-8")
        open(ruta, "wb").write(texto.replace(", 6X", ", 10X").encode("utf-8"))
    p = fabrica()
    assert p.combo_energia.currentText() == ENERGIA
    d = abrir(p)
    d.linea_energia.setText("")
    elegir(list(reales.values()))
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert d.linea_energia.text() == "10 MV" and d.boton_guardar.isEnabled()
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert [p.combo_energia.itemText(i) for i in range(p.combo_energia.count())] == [ENERGIA, "10 MV"] and p.combo_energia.currentText() == "10 MV"
    assert _sql(bd, "SELECT energia, activo FROM um_datos_haz ORDER BY id") == [(ENERGIA, 1), ("10 MV", 1)]


# ================================================================================================================================== lo que no deja guardar, y lo que avisa

def _no_guarda(d, bd):
    assert not d.boton_guardar.isEnabled() and d._revisada is None and d.estado.text().startswith("No se puede guardar: ")
    estado = d.estado.text()
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    d.guardar()                       # ni llamado directamente: sin una revisión sin problemas no hace nada
    assert _sql(bd, "SELECT COUNT(*) FROM um_datos_haz") == [(0,)] and d.estado.text() == estado


def test_un_archivo_cortado_se_rechaza_con_su_motivo_y_los_demas_siguen_en_el_resumen(bd_vacia, fabrica, elegir, reales):
    cortar(reales[OPD])
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    problemas = items(d.lista_problemas)
    assert len(problemas) == 1 and problemas[0].startswith(f"{OPD}: ") and reales[OPD] not in problemas[0]       # el motivo nombra el archivo, por su nombre corto (UM.2b)
    vistas = {f[0]: f[2] for f in filas(d.tabla_archivos)}
    assert vistas[OPD] == "Impide guardar: vea el motivo" and sum(e == "Se usa" for e in vistas.values()) == USADOS - 1 and len(vistas) == 22
    assert d.etiqueta_conteo.text() == "22 archivos: 11 se usan, 10 se ignoran y 1 impide guardar."      # UM5-S8 (clase b): el PDD cortado impide guardar y suma el total (11 + 10 + 1 = 22)
    _no_guarda(d, bd_vacia)


@pytest.mark.parametrize("equipo, energia, dice", [("Clinac iX", ENERGIA, "dice máquina 600C, y se está cargando para Clinac iX."),
                                                   (EQUIPO, "10 MV", "dice haz 6X, y se está cargando para 10 MV.")])
def test_otra_maquina_u_otra_energia_reconocidas_no_dejan_guardar(bd_vacia, fabrica, elegir, reales, equipo, energia, dice):
    p = fabrica()
    d = abrir(p)
    d.combo_equipo.setCurrentIndex(d.combo_equipo.findText(equipo))
    d.linea_energia.setText(energia)
    elegir(list(reales.values()))
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert d.linea_energia.text() == energia                  # una energía escrita no se cambia por la de los archivos
    assert items(d.lista_problemas) == [f"{nombre} {dice}" for nombre in reales if _lo_que_dice_a_mano(nombre)[1] == "Se usa"]
    assert [f[2] for f in filas(d.tabla_archivos)].count("Impide guardar: vea el motivo") == USADOS and "Se usa" not in [f[2] for f in filas(d.tabla_archivos)]
    _no_guarda(d, bd_vacia)


def test_un_nombre_de_maquina_que_no_se_reconoce_avisa_y_deja_guardar(bd_vacia, fabrica, elegir, reales):
    renombrar_maquina(reales.values(), "SALA 3")
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    aviso = "dice máquina SALA 3, que este lector no reconoce: compruebe que es de Clinac 600."
    assert [a for a in items(d.lista_avisos) if aviso in a] == [f"{n} {aviso}" for n in reales if _lo_que_dice_a_mano(n)[1] == "Se usa"]
    assert items(d.lista_problemas) == [carga.NADA_IMPIDE] and d.boton_guardar.isEnabled()
    assert filas(d.tabla_archivos)[2][1] == "máquina SALA 3, haz 6X; Open Field - 00: PDD medido"
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert _sql(bd_vacia, "SELECT equipo FROM um_datos_haz") == [(EQUIPO,)]


@pytest.mark.parametrize("falta", [OPD, OF_ABIERTA])
def test_sin_pdd_o_sin_tabla_abierta_no_se_guarda(bd_vacia, fabrica, elegir, reales, falta):
    p = fabrica()
    d = con_archivos(p, elegir, [r for n, r in reales.items() if n != falta])
    assert items(d.lista_problemas) == ["faltan el PDD medido o la tabla de factores del campo abierto"]
    _no_guarda(d, bd_vacia)


def test_la_prueba_de_filas_y_columnas_cae_si_se_traspone_la_tabla_de_la_cuna_con_name_data(bd_vacia, fabrica, elegir, reales):
    """H4 (b): la tabla de la cuña de 15° dice IN en su name.data y tiene el lado corto en Y; traspuesta, el lado corto queda en X y no se puede guardar."""
    trasponer_tabla(reales[OF_15])
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    assert items(d.lista_problemas) == [f"{OF_15} y name.data: la cuña de 15° dice orientación IN y su tabla tiene el lado corto en X: filas y columnas no cuadran"]
    _no_guarda(d, bd_vacia)


@pytest.mark.parametrize("angulo, corto", [(30, 20), (45, 20), (60, 15)])
def test_la_tabla_traspuesta_de_una_cuna_sin_name_data_tampoco_se_guarda(bd_vacia, fabrica, elegir, reales, angulo, corto):
    """Sin name.data, lo que delata la tabla traspuesta es su PDD con cuña, medido en el campo entero (40 × lado corto) que la tabla ya no tiene."""
    of, wdd = f"CLINAC 600C_Standard Wedge - {angulo}_Output Factors.txt", f"CLINAC 600C_Standard Wedge - {angulo}_Measured Wedge Depth Doses.txt"
    trasponer_tabla(reales[of])
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    assert items(d.lista_problemas) == [f"{wdd} y {of}: la cuña de {angulo}°: hay un PDD con cuña de 40 × {corto} [cm], que no es un cuadrado ni el campo entero de su tabla "
                                        f"({corto} × 40 [cm]): revise ese PDD y la tabla de factores de la cuña, que puede estar cortada al final de una fila"]
    _no_guarda(d, bd_vacia)


def test_d0_fuera_de_lo_posible_no_deja_guardar(bd_vacia, fabrica, elegir, reales):
    p = fabrica()
    d = abrir(p)
    d.linea_d0.setText("2")
    elegir(list(reales.values()))
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert items(d.lista_problemas) == ["D'0 no es un valor posible (de 0.5 a 1.5 [cGy/UM]): 2.0"]
    _no_guarda(d, bd_vacia)


def test_d0_en_las_condiciones_de_la_tabla_y_el_factor_escrito_de_una_cuna(bd_vacia, fabrica, elegir, reales):
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    d.linea_d0.setText("")
    QTest.keyClicks(d.linea_d0, "0,86")
    d.combo_d0.setCurrentIndex(d.combo_d0.findText(carga.D0_EN_LA_TABLA))
    d.linea_origen.setText("")
    QTest.keyClicks(d.linea_origen, "medido el 05-11")
    QTest.keyClicks(d.campos_wf[30], "0.61")
    QTest.mouseClick(d.boton_revisar, Qt.LeftButton)
    avisos = items(d.lista_avisos)
    assert "D'0 = 0.8600 [cGy/UM] a 5 [cm] de profundidad, SSD 100 [cm], 10 × 10, escrito en las condiciones de la tabla." in avisos
    assert "Cuña de 30°: falta su factor en 10 × 10; hasta tenerlo se escribe por campo." not in avisos
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert _sql(bd_vacia, "SELECT d0_dmax, d0_tabla, d0_origen, wf_escritos FROM um_datos_haz") == [(None, 0.86, "medido el 05-11", '{"30": 0.61}')]
    assert calcular(p, {"x": "10", "y": "10", "ssd": "100", "prof": "10"}, 30, "IN").startswith("UM calculadas: ")


def test_un_factor_escrito_imposible_no_deja_guardar(bd_vacia, fabrica, elegir, reales):
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    QTest.keyClicks(d.campos_wf[45], "7")
    QTest.mouseClick(d.boton_revisar, Qt.LeftButton)
    (problema,) = items(d.lista_problemas)
    assert "45°" in problema and "no es un valor posible" in problema
    _no_guarda(d, bd_vacia)


def test_lo_escrito_que_no_se_entiende_no_se_revisa_y_lo_dice(bd_vacia, fabrica, elegir, reales, monkeypatch):
    revisiones = espia(monkeypatch, "revisar")
    p = fabrica()
    d = abrir(p)
    d.linea_d0.setText("uno")
    elegir(list(reales.values()))
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert revisiones == [] and items(d.lista_problemas) == ["No se entiende D'0 [cGy/UM]: «uno». Escriba solo el número, con punto o coma decimal y sin unidades."]
    assert {f[2] for f in filas(d.tabla_archivos)} == {carga.SIN_REVISAR} and len(filas(d.tabla_archivos)) == 22 and d.etiqueta_conteo.text() == "22 archivos: sin revisar."
    assert d.etiqueta_vigente.text() == "" and items(d.lista_avisos) == []
    _no_guarda(d, bd_vacia)


def test_un_archivo_que_no_se_lee_impide_guardar_y_los_demas_se_revisan(bd_vacia, fabrica, elegir, reales, tmp_path):
    p = fabrica()
    perdido = str(tmp_path / "perdido.txt")
    d = con_archivos(p, elegir, list(reales.values()) + [perdido])
    assert items(d.lista_problemas) == ["perdido.txt: no se pudo leer (No such file or directory)"]
    assert filas(d.tabla_archivos)[-1] == ("perdido.txt", "no se pudo leer (No such file or directory)", "Impide guardar: no se leyó")
    assert d.etiqueta_conteo.text() == "23 archivos: 12 se usan y 10 se ignoran; 1 no se pudo leer."
    _no_guarda(d, bd_vacia)


def test_un_archivo_guardado_como_unicode_impide_revisar_y_los_demas_se_ven(bd_vacia, fabrica, elegir, reales):
    texto = open(reales[OF_ABIERTA], encoding="utf-8-sig").read()
    open(reales[OF_ABIERTA], "wb").write(texto.encode("utf-16"))
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    (problema,) = items(d.lista_problemas)
    assert problema.startswith(f"{OF_ABIERTA}: el archivo trae bytes nulos")
    vistas = {f[0]: f for f in filas(d.tabla_archivos)}
    assert vistas[OF_ABIERTA][1].startswith("No se entiende su cabecera: el archivo trae bytes nulos") and vistas[OF_ABIERTA][2] == "Impide guardar: vea el motivo"
    assert {f[2] for n, f in vistas.items() if n != OF_ABIERTA} == {"Sin revisar: lo impide otro problema"} and len(vistas) == 22
    assert d.etiqueta_conteo.text() == "22 archivos: sin revisar."
    _no_guarda(d, bd_vacia)


def test_dos_archivos_con_el_mismo_nombre_en_carpetas_distintas_se_distinguen(bd_vacia, fabrica, elegir, reales, tmp_path):
    otra = tmp_path / "copia_15"
    otra.mkdir()
    shutil.copy(reales["name.data"], otra / "name.data")
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()) + [str(otra / "name.data")])
    assert "copia_15/name.data: es copia idéntica de exportados/name.data: se usa una sola vez." in items(d.lista_avisos)
    assert [f[0] for f in filas(d.tabla_archivos)].count("exportados/name.data") == 1 and d.boton_guardar.isEnabled()


def test_elegir_y_cancelar_no_cambia_nada(bd_vacia, fabrica, elegir):
    p = fabrica()
    d = abrir(p)
    assert d.estado.text() == carga.SIN_ARCHIVOS and not d.boton_guardar.isEnabled() and d.tabla_archivos.rowCount() == 0
    assert not d.titulo_cunas.isVisibleTo(d) and d.titulo_problemas.text() == "Lo que impide guardar" and d.titulo_avisos.text() == "Lo que entendió la app y conviene mirar"
    assert [d.tabla_archivos.columnWidth(j) for j in range(2)] == list(carga.ANCHOS_DE_LOS_ARCHIVOS)
    elegir([])
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert d.estado.text() == carga.SIN_ARCHIVOS and d.archivos == [] and not d.boton_guardar.isEnabled()
    QTest.mouseClick(d.boton_revisar, Qt.LeftButton)
    assert d.estado.text() == carga.SIN_ARCHIVOS and not d.boton_guardar.isEnabled()


def test_elegir_otra_vez_reemplaza_la_lista_y_conserva_el_factor_escrito(bd_vacia, fabrica, elegir, reales):
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    QTest.keyClicks(d.campos_wf[30], "0.6")
    elegir([r for n, r in reales.items() if "Wedge - 60" not in n])
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert sorted(d.campos_wf) == [15, 30, 45] and d.campos_wf[30].text() == "0.6" and len(filas(d.tabla_archivos)) == 18
    assert d.boton_guardar.isEnabled()


# ================================================================================================================================== el permiso del servicio y los errores inesperados

def test_si_el_servicio_niega_el_permiso_la_pantalla_dice_el_motivo_sin_numero_ni_simbolo(bd_vacia, fabrica, elegir, reales, monkeypatch):
    """La pantalla solo pinta el botón: si la cuenta no puede (aquí se fuerza el botón para la física de turno, como si su rol hubiera cambiado), el servicio lo niega y lo audita."""
    monkeypatch.setattr(carga, "puede_cargar", lambda login: True)
    p = fabrica(Usuario(username="fisica"))
    d = con_archivos(p, elegir, list(reales.values()))
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert d.estado.text() == "No se guardó nada: solo el físico jefe o el administrador pueden cargar las tablas de un acelerador"
    assert not re.search(r"[0-9]", d.estado.text()) and not SIMBOLOS.search(d.estado.text())
    assert _sql(bd_vacia, "SELECT COUNT(*) FROM um_datos_haz") == [(0,)] and p.combo_energia.count() == 0
    assert _sql(bd_vacia, "SELECT usuario, detalle FROM audit_log WHERE tabla = 'um_datos_haz'") == [("Física de Turno", um_datos_haz.DENEGADO)]


def test_un_error_inesperado_al_revisar_se_dice_y_no_deja_guardar(bd_vacia, fabrica, elegir, reales, monkeypatch):
    def rota(**k):
        raise RuntimeError("se cayó")
    monkeypatch.setattr(um_datos_haz, "revisar", rota)
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    assert items(d.lista_problemas) == ["La revisión falló por un error inesperado (RuntimeError: se cayó). Avise a quien mantiene la app."]
    assert QApplication.overrideCursor() is None
    _no_guarda(d, bd_vacia)


def test_un_error_inesperado_al_guardar_se_dice_y_la_pestana_no_cambia(bd_vacia, fabrica, elegir, reales, monkeypatch):
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))

    def roto(**k):
        raise RuntimeError("disco")
    monkeypatch.setattr(um_datos_haz, "guardar", roto)
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert d.estado.text() == ("No se guardó nada: el guardado falló por un error inesperado (RuntimeError: disco); mire el historial antes de volver a intentarlo y avise a quien mantiene "
                               "la app")
    assert p.combo_energia.count() == 0 and not d.boton_guardar.isEnabled() and QApplication.overrideCursor() is None


def test_no_saber_si_hay_tablas_vigentes_no_impide_revisar(bd_vacia, fabrica, elegir, reales, monkeypatch):
    def rota(*a, **k):
        raise um_datos_haz.DatosHazError("la base no se abre")
    monkeypatch.setattr(um_datos_haz, "vigente", rota)
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    assert d.etiqueta_vigente.text() == "No se pudo saber si ya hay tablas vigentes del Clinac 600, 6 MV: la base no se abre" and d.boton_guardar.isEnabled()


# ================================================================================================================================== el historial, la ventana y los textos

def test_el_historial_sin_tablas_lo_dice(bd_vacia, fabrica):
    p = fabrica()
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    h = p.dialogo_historial
    assert h.aviso.text() == "No hay tablas cargadas del Clinac 600: no hay historial." and h.tabla.rowCount() == 0 and h.windowTitle() == carga.TITULO_DEL_HISTORIAL


def test_el_historial_que_no_se_puede_leer_lo_dice(bd, fabrica, monkeypatch):
    def roto(*a):
        raise um_datos_haz.DatosHazError("sin base")
    p = fabrica()
    monkeypatch.setattr(um_datos_haz, "historial", roto)
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    assert p.dialogo_historial.aviso.text() == "No se pudo leer el historial del Clinac 600, 6 MV: sin base" and p.dialogo_historial.tabla.rowCount() == 0


def test_abrir_otra_vez_suelta_el_dialogo_anterior(bd, fabrica):
    p = fabrica()
    primero = abrir(p)
    primero.close()
    segundo = abrir(p)
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert segundo is not primero and sip.isdeleted(primero) and segundo.linea_energia.text() == ENERGIA      # arranca con la energía elegida en la pestaña
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    h1 = p.dialogo_historial
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert sip.isdeleted(h1) and p.dialogo_historial.isVisible()


def test_los_dialogos_se_destruyen_con_la_pestana(bd, app):
    p = pantalla.CalculadoraUM("jefa")
    d = abrir(p)
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    h = p.dialogo_historial
    cerrar(p)
    assert sip.isdeleted(d) and sip.isdeleted(h)


def test_ningun_texto_lleva_simbolos_parentesis_de_unidades_ni_ids(bd_vacia, fabrica, elegir, reales):
    cortar(reales[OPD])
    p = fabrica(Usuario(username="fisica"))
    textos = [p.boton_cargar.toolTip(), p.boton_historial.toolTip(), p.aviso_tablas.text()]
    q = fabrica()
    d = con_archivos(q, elegir, list(reales.values()))
    textos += textos_que_se_ven(d)
    textos += [v for k, v in vars(carga).items() if k.isupper() and isinstance(v, str)] + list(carga.QUE_ES.values())
    for texto in textos:
        assert not SIMBOLOS.search(texto) and not ENTRE_PARENTESIS.search(texto), texto
        assert not re.search(r"\b(UM\d|DC\d+|DA-\d+|DP-\d+|PC-\d+|H\d+|UM5-D\d+)\b", texto), texto


def test_el_dialogo_cabe_y_sus_listas_se_leen_enteras(bd_vacia, fabrica, elegir, reales):
    from PyQt5.QtWidgets import QAbstractItemView
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    assert (d.width(), d.height()) == carga.TAMANO_DE_LA_CARGA and d.width() <= 1366 and d.height() <= 768 - 40
    for lista in (d.lista_problemas, d.lista_avisos):
        assert lista.wordWrap() and lista.verticalScrollMode() == QAbstractItemView.ScrollPerPixel
    assert d.lista_problemas.minimumHeight() >= 3 * carga.ALTO_DE_UNA_FILA and d.lista_problemas.height() >= 3 * carga.ALTO_DE_UNA_FILA
    assert d.estado.wordWrap() and d.etiqueta_vigente.wordWrap() and d.nota_filas_y_columnas.wordWrap()
    assert d.tabla_archivos.editTriggers() == d.tabla_archivos.NoEditTriggers
    assert all(d.tabla_archivos.item(i, j).toolTip() == d.tabla_archivos.item(i, j).text() for i in range(22) for j in range(3))


# ================================================================================================================================== sin hilo (H14)

def test_el_resumen_de_los_22_reales_sale_rapido(bd_vacia, fabrica, elegir, reales):
    """Sin hilo: medido en el pre-vuelo, unas décimas de segundo; el tope deja margen para una máquina cargada."""
    p = fabrica()
    d = abrir(p)
    elegir(list(reales.values()))
    t = time.perf_counter()
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert time.perf_counter() - t < 5.0 and d.boton_guardar.isEnabled()


def test_un_archivo_de_5_mb_no_congela_y_se_rechaza_con_su_motivo(bd_vacia, fabrica, elegir, reales, tmp_path):
    """Un archivo de 5 [MB] con la cabecera de Eclipse (los perfiles repetidos hasta llenarlo): el resumen sale en segundos y dice qué tiene."""
    perfiles = reales["CLINAC 600C_Open Field - 00_Processed Measured Profiles.txt"]
    grande = tmp_path / "grande.txt"
    contenido = open(perfiles, "rb").read()
    grande.write_bytes(contenido * (5 * 1024 * 1024 // len(contenido) + 1))
    assert grande.stat().st_size > 5 * 1024 * 1024
    p = fabrica()
    d = abrir(p)
    elegir([r for n, r in reales.items() if "Processed" not in n] + [str(grande)])
    t = time.perf_counter()
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert time.perf_counter() - t < 15.0
    assert any(problema.startswith("grande.txt: ") for problema in items(d.lista_problemas))
    _no_guarda(d, bd_vacia)


# ================================================================================================================================== el empaquetado

def test_el_conteo_cuenta_si_el_servicio_clasifico_los_archivos_aunque_haya_un_problema():
    """Barrido de la fase 2 (L200): «sin revisar» solo cuando el servicio no clasificó NINGUNO; con un problema y solo usados, o con un problema y solo ignorados, se cuenta (UM5-S8: el nombrado en
    el problema impide guardar y no se cuenta como usado; un problema que no nombra ningún archivo no mueve a ninguno)."""
    from services.um_armar import Revision
    archivos = [("/d/a", b""), ("/d/b", b"")]
    otra = Revision(("/d/a", "/d/b"), (), ("/d/b dice máquina X, y se está cargando para Clinac 600.",), ())
    assert carga.texto_del_conteo(archivos, [], otra) == "2 archivos: 1 se usa, 0 se ignoran y 1 impide guardar."      # UM5-S8 (clase b)
    assert carga.texto_del_conteo(archivos, [], Revision((), ("/d/a", "/d/b"), ("Falta el PDD medido del campo abierto.",), ())) == "2 archivos: 0 se usan y 2 se ignoran."


def test_una_energia_de_solo_espacios_es_una_energia_que_falta():
    """Barrido de la fase 2 (L146): lo que se ve vacío dice «Falta escribir la energía», no «No se entiende la energía «»»."""
    with pytest.raises(motor.FaltaDato) as fallo:
        carga.carga_desde_textos(**_textos(energia="   "))
    assert str(fallo.value) == "Falta escribir la energía, por ejemplo «6 MV»."


def test_un_archivo_que_mide_justo_el_tope_se_lee(tmp_path, monkeypatch):
    """Barrido de la fase 2 (L81): el tope es «más de 20 [MB]»; uno que mide exactamente el tope se lee."""
    justo = tmp_path / "justo.txt"
    justo.write_bytes(b"abc")
    real = os.path.getsize
    monkeypatch.setattr(carga.os.path, "getsize", lambda r: carga.TAMANO_MAXIMO_BYTES if r == str(justo) else real(r))
    assert carga.leer_archivos([str(justo)]) == ([(str(justo), b"abc")], [])


def test_una_ruta_hecha_solo_de_separadores_se_muestra_tal_cual():
    """Barrido de la fase 2 (L101): el selector no la da, pero si llega no rompe el resumen: se ve como es."""
    assert carga.nombres_para_mostrar(["/", "\\"]) == {"/": "/", "\\": "\\"}


def test_dos_maneras_de_escribir_la_misma_ruta_se_ven_igual_y_no_cuelgan():
    """Barrido de la fase 2 (L110, el primer operando del `and`): con las mismas partes, el bucle se detiene en la ruta entera (sin ese tope no terminaría)."""
    assert carga.nombres_para_mostrar(["/d/a.txt", "/d//a.txt", "C:\\d\\a.txt"]) == {"/d/a.txt": "d/a.txt", "/d//a.txt": "d/a.txt", "C:\\d\\a.txt": "C:/d/a.txt"}


def test_build_exe_lista_el_dialogo_una_vez_y_sigue_en_crlf():
    import ast
    crudo = open(os.path.join(RAIZ, "build_exe.py"), "rb").read()
    assert b"\r\n" in crudo and b"\n" not in crudo.replace(b"\r\n", b""), "build_exe.py sigue en CRLF"
    arbol = ast.parse(crudo.decode("utf-8"))
    lista = next(n.value for n in arbol.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "hidden_imports" for t in n.targets))
    nombres = [e.value for e in lista.elts]
    assert nombres.count("ui.paginasGuia.calculadora_um_cargar") == 1
    assert nombres.index("ui.paginasGuia.calculadora_um_cargar") == nombres.index("ui.paginasGuia.calculadora_um") + 1
    assert os.path.exists(os.path.join(RAIZ, "ui", "paginasGuia", "calculadora_um_cargar.py"))


def test_el_dialogo_no_tiene_sql_ni_fisica():
    """DC16: sin SQL ni conexiones propias (todo por el servicio) y sin la ecuación (la pestaña llama al motor)."""
    import ast
    fuente = open(os.path.join(RAIZ, "ui", "paginasGuia", "calculadora_um_cargar.py"), encoding="utf-8").read()
    arbol = ast.parse(fuente)
    importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
    assert not {m for m in importados if m and (m.startswith("sqlite3") or m.startswith("data") or "matplotlib" in m or m == "services.um_armar")}
    assert not re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", fuente) and "conectar(" not in fuente and "calcular(" not in fuente


# ================================================================================================================================== UM.5, suplemento: la segunda vuelta de la auditoría de UM.4 (S1 y S2 en el diálogo)

def _minimo_tras_revisar(p, elegir, rutas):
    d = abrir(p)
    d.linea_energia.setText(ENERGIA)
    elegir(rutas)
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    QApplication.processEvents()
    return d, d.minimumSizeHint().width()


def test_s1_un_nombre_de_archivo_enorme_no_ensancha_el_dialogo(bd_vacia, fabrica, elegir, tmp_path):
    """UM5-S1 en el diálogo: un archivo cuyo nombre (el más largo posible, sin espacios) sale en la tabla, en lo que impide guardar y en el estado no cambia el ancho mínimo del diálogo."""
    corto, largo = tmp_path / "a.txt", tmp_path / ("A" * 120 + "B" * 120 + ".txt")
    for archivo in (corto, largo):
        archivo.write_text("no es de Eclipse", encoding="utf-8")
    _, con_el_corto = _minimo_tras_revisar(fabrica(), elegir, [str(corto)])
    d, con_el_largo = _minimo_tras_revisar(fabrica(), elegir, [str(largo)])
    assert con_el_largo == con_el_corto and items(d.lista_problemas)[0].startswith("A" * 120)


def test_s1_un_rechazo_que_nombra_un_archivo_enorme_se_ve_acortado_y_no_ensancha(bd_vacia, fabrica, elegir, reales, monkeypatch):
    p = fabrica()
    d = con_archivos(p, elegir, list(reales.values()))
    QApplication.processEvents()
    antes = d.minimumSizeHint().width()
    monkeypatch.setattr(um_datos_haz, "guardar", lambda **k: (False, um_datos_haz.NO_SE_GUARDA + "Z" * 240 + ".txt: parece cortado", None))
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    QApplication.processEvents()
    assert d.estado.text().startswith("No se guardó nada: ZZZZZZZZZZ…") and d.estado.text().endswith("parece cortado") and d.minimumSizeHint().width() == antes


def test_s1_las_etiquetas_de_los_dialogos_siguen_la_regla_comun(bd, fabrica):
    p = fabrica()
    d = abrir(p)
    assert set(d.etiquetas_que_cambian) == {d.nota_filas_y_columnas, d.etiqueta_vigente, d.estado, d.etiqueta_conteo}       # R1-S8b: el conteo también (su texto ya no es corto)
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    for etiqueta in list(d.etiquetas_que_cambian) + [p.dialogo_historial.aviso]:
        assert etiqueta.wordWrap() and etiqueta.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding and etiqueta.sizePolicy().verticalPolicy() == QSizePolicy.Preferred


def test_s1_un_fallo_enorme_del_historial_se_ve_acortado_y_no_ensancha(bd, fabrica, monkeypatch):
    p = fabrica()
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    QApplication.processEvents()
    sano = p.dialogo_historial.minimumSizeHint().width()

    def roto(*a):
        raise um_datos_haz.DatosHazError("x" * 400)
    monkeypatch.setattr(um_datos_haz, "historial", roto)
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    QApplication.processEvents()
    h = p.dialogo_historial
    assert "…" in h.aviso.text() and h.minimumSizeHint().width() <= sano


def test_s2_ningun_panel_del_resumen_se_colapsa(bd_vacia, fabrica, elegir, reales):
    from PyQt5.QtWidgets import QSplitter
    d = con_archivos(fabrica(), elegir, list(reales.values()))
    (divisor,) = d.findChildren(QSplitter)
    assert not divisor.childrenCollapsible()
    total = sum(divisor.sizes())
    for extremo in ([total, 0, 0], [0, total, 0], [0, 0, total]):
        divisor.setSizes(extremo)
        QApplication.processEvents()
        assert min(divisor.sizes()) > 0, divisor.sizes()


# ================================================================================================================================== UM5-S8: el conteo de archivos suma el total (PC-28)

# Lo que dice la tabla de cada archivo según lo que es (escrito aquí tal cual, no tomado del módulo): el conteo y la tabla salen de UNA clasificación y no pueden contradecirse.
TEXTOS_DE_LA_TABLA = {"usa": "Se usa", "ignora": "Se ignora: el cálculo no lo lee", "impide": "Impide guardar: vea el motivo", "sin": "Sin revisar: lo impide otro problema"}


def _eleccion(u=0, i=0, p=0, s=0, n=0, cortada=False):
    """Una elección de archivos y lo que el servicio diría de ella, armada POR CONSTRUCCIÓN (la clase de cada archivo se sabe de antemano, no se lee de la revisión): `u` se usan, `i` se
    ignoran, `p` están nombrados en un problema (de a tres: uno que el servicio usaría, como una tabla de otra máquina, uno que ignoraría y uno que no clasificó, como un PDD cortado; con
    `cortada` todos del tercer tipo), `s` no están en ninguna lista ni en ningún problema y `n` no se pudieron leer. -> (archivos, no_leidos, revision, clase de cada archivo en su orden)."""
    from services.um_armar import Revision
    por_clase = {"usa": [f"/d/usa{k:02d}" for k in range(u)], "ignora": [f"/d/ignora{k:02d}" for k in range(i)], "impide": [f"/d/impide{k:02d}" for k in range(p)],
                 "sin": [f"/d/sin{k:02d}" for k in range(s)]}
    usados, ignorados, problemas = list(por_clase["usa"]), list(por_clase["ignora"]), []
    for k, ruta in enumerate(por_clase["impide"]):
        tipo = 2 if cortada else k % 3
        if tipo == 0:
            usados.append(ruta)
            problemas.append(f"{ruta} dice máquina X, y se está cargando para Clinac 600.")
        elif tipo == 1:
            ignorados.append(ruta)
            problemas.append(f"{ruta}: hay dos archivos distintos para Open Field - 00, PDD medido")
        else:
            problemas.append(f"{ruta}: cortado")
    orden = [(clase, ruta) for k in range(max(u, i, p, s)) for clase in ("sin", "impide", "ignora", "usa") for ruta in por_clase[clase][k:k + 1]]      # intercalados: el orden no ayuda a la cuenta
    return ([(ruta, b"") for _, ruta in orden], [(f"/d/leer{k:02d}", "no se pudo leer (x)") for k in range(n)], Revision(tuple(usados), tuple(ignorados), tuple(problemas), ()),
            [clase for clase, _ in orden])


def _conteo_de_referencia(total, usan, ignoran, impiden, sin_leer, sin_revisar):
    """El texto que pide UM5-S8, escrito aparte del módulo (la prueba es la especificación): sin nada que impida guardar, el de siempre; con algo, los cuatro números suman el total."""
    cuerpo = "sin revisar" if sin_revisar else (f"{usan} se {'usa' if usan == 1 else 'usan'} y {ignoran} se {'ignora' if ignoran == 1 else 'ignoran'}" if not impiden else
                                                f"{usan} se {'usa' if usan == 1 else 'usan'}, {ignoran} se {'ignora' if ignoran == 1 else 'ignoran'} y {impiden} {'impide' if impiden == 1 else 'impiden'} guardar")
    return f"{total} {'archivo' if total == 1 else 'archivos'}: {cuerpo}" + (f"; {sin_leer} no se {'pudo' if sin_leer == 1 else 'pudieron'} leer." if sin_leer else ".")


@pytest.mark.parametrize("u, i, p, s, n, texto", [
    (1, 1, 1, 0, 0, "3 archivos: 1 se usa, 1 se ignora y 1 impide guardar."),
    (2, 3, 2, 0, 0, "7 archivos: 2 se usan, 3 se ignoran y 2 impiden guardar."),
    (0, 0, 0, 1, 0, "1 archivo: 0 se usan, 0 se ignoran y 1 impide guardar."),
    (0, 2, 0, 3, 1, "6 archivos: 0 se usan, 2 se ignoran y 3 impiden guardar; 1 no se pudo leer."),
    (1, 0, 1, 1, 2, "5 archivos: 1 se usa, 0 se ignoran y 2 impiden guardar; 2 no se pudieron leer."),
    (10, 10, 2, 0, 0, "22 archivos: 10 se usan, 10 se ignoran y 2 impiden guardar."),
])
def test_s8_con_algo_que_impide_guardar_el_conteo_lo_dice_en_singular_o_en_plural(u, i, p, s, n, texto):
    archivos, no_leidos, revision, _ = _eleccion(u, i, p, s, n)
    assert carga.texto_del_conteo(archivos, no_leidos, revision) == texto


def test_s8_una_sola_clasificacion_da_las_filas_de_la_tabla_y_el_conteo():
    from services.um_armar import Revision
    archivos = [("/d/a", b""), ("/d/b", b""), ("/d/c", b""), ("/d/e", b""), ("/d/g", b""), ("/d/g.txt", b"")]
    revision = Revision(("/d/a", "/d/g", "/d/g.txt"), ("/d/b",), ("/d/c: cortado", "/d/g.txt dice máquina X, y se está cargando para Clinac 600."), ())
    estados = carga.estado_de_cada_archivo(archivos, revision)
    assert estados == [carga.USA, carga.IGNORA, carga.IMPIDE, carga.SIN_CLASIFICAR, carga.USA, carga.IMPIDE]       # «/d/g» se usa y «/d/g.txt» impide: el nombre se busca entero
    assert len({carga.USA, carga.IGNORA, carga.IMPIDE, carga.SIN_CLASIFICAR}) == 4
    assert carga.estado_de_cada_archivo(archivos, None) is None and carga.estado_de_cada_archivo([], revision) == []
    cortos = carga.nombres_para_mostrar([ruta for ruta, _ in archivos])
    assert [f[2] for f in carga.filas_de_los_archivos(archivos, [], {ruta: "" for ruta, _ in archivos}, revision, cortos)] == [
        "Se usa", "Se ignora: el cálculo no lo lee", "Impide guardar: vea el motivo", "Sin revisar: lo impide otro problema", "Se usa", "Impide guardar: vea el motivo"]
    assert carga.texto_del_conteo(archivos, [], revision) == "6 archivos: 2 se usan, 1 se ignora y 3 impiden guardar."


def test_s8_sin_nada_que_impida_guardar_el_conteo_es_el_de_antes_byte_a_byte():
    from services.um_armar import Revision
    a = [("/d/a", b""), ("/d/b", b"")]
    assert carga.texto_del_conteo(a[:1], [], Revision(("/d/a",), (), (), ())) == "1 archivo: 1 se usa y 0 se ignoran."
    assert carga.texto_del_conteo(a, [], Revision(("/d/a",), ("/d/b",), (), ())) == "2 archivos: 1 se usa y 1 se ignora."
    assert carga.texto_del_conteo(a, [("/d/f", "")], Revision(("/d/a", "/d/b"), (), (), ())) == "3 archivos: 2 se usan y 0 se ignoran; 1 no se pudo leer."
    assert carga.texto_del_conteo([], [("/d/f", ""), ("/d/g", "")], Revision((), (), (), ())) == "2 archivos: 0 se usan y 0 se ignoran; 2 no se pudieron leer."
    assert carga.texto_del_conteo(a, [], Revision((), ("/d/a", "/d/b"), ("Falta el PDD medido del campo abierto.",), ())) == "2 archivos: 0 se usan y 2 se ignoran."      # un problema que no nombra ningún archivo no mueve a ninguno
    assert carga.texto_del_conteo(a, [], Revision((), (), ("/d/a: bytes nulos",), ())) == "2 archivos: sin revisar."          # el servicio cortó la revisión: sin revisar, como siempre
    assert carga.texto_del_conteo(a, [("/d/f", "")], None) == "3 archivos: sin revisar; 1 no se pudo leer."


def test_s8_un_pdd_cortado_y_una_tabla_de_otra_maquina_suman_los_22_en_el_conteo(bd_vacia, fabrica, elegir, reales):
    """El caso que midió el pre-vuelo con el servicio sobre copias de los 22 reales: un PDD cortado (el servicio no lo clasifica) y una tabla de otra máquina (el servicio la usaría). El conteo
    decía «22 archivos: 11 se usan y 10 se ignoran.» (11 + 10 = 21) mientras la tabla decía «Impide guardar» para los dos."""
    cortar(reales[OPD])
    renombrar_maquina([reales[OF_15]], "iX")
    d = con_archivos(fabrica(), elegir, list(reales.values()))
    vistas = {f[0]: f[2] for f in filas(d.tabla_archivos)}
    assert vistas[OPD] == vistas[OF_15] == "Impide guardar: vea el motivo" and sum(e == "Se usa" for e in vistas.values()) == 10 and len(vistas) == 22
    assert d.etiqueta_conteo.text() == "22 archivos: 10 se usan, 10 se ignoran y 2 impiden guardar."
    numeros = [int(x) for x in re.findall(r"\d+", d.etiqueta_conteo.text())]
    assert numeros[0] == sum(numeros[1:]) == 22
    _no_guarda(d, bd_vacia)


@pytest.mark.parametrize("equipo, energia", [("Clinac iX", ENERGIA), (EQUIPO, "10 MV")])
def test_s8_con_otra_maquina_u_otra_energia_el_conteo_dice_cuantos_impiden_guardar(bd_vacia, fabrica, elegir, reales, equipo, energia):
    d = abrir(fabrica())
    d.combo_equipo.setCurrentIndex(d.combo_equipo.findText(equipo))
    d.linea_energia.setText(energia)
    elegir(list(reales.values()))
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert d.etiqueta_conteo.text() == "22 archivos: 0 se usan, 10 se ignoran y 12 impiden guardar."       # los 12 que se usarían dan el problema de la otra máquina o la otra energía
    assert sum(fila[2] == "Impide guardar: vea el motivo" for fila in filas(d.tabla_archivos)) == 12


def test_s8_un_archivo_que_no_se_lee_va_aparte_del_que_impide_guardar(bd_vacia, fabrica, elegir, reales, tmp_path):
    cortar(reales[OPD])
    d = con_archivos(fabrica(), elegir, list(reales.values()) + [str(tmp_path / "perdido.txt")])
    assert d.etiqueta_conteo.text() == "23 archivos: 11 se usan, 10 se ignoran y 1 impide guardar; 1 no se pudo leer."
    numeros = [int(x) for x in re.findall(r"\d+", d.etiqueta_conteo.text())]
    assert numeros[0] == sum(numeros[1:]) == len(filas(d.tabla_archivos)) == 23


def test_s8_el_conteo_suma_el_total_y_coincide_con_la_tabla_para_toda_eleccion():
    """Todas las combinaciones de 0 a 3 archivos de cada clase (se usan, se ignoran, impiden por un problema, sin clasificar, no leídos), con el servicio completo y con el servicio que cortó la
    revisión sin clasificar ninguno: usan + ignoran + impiden + no leídos = el total, y el número de los que impiden es el de filas de la tabla que dicen que impiden. «Sin revisar» solo cuando
    el servicio cortó la revisión Y dejó algún archivo sin veredicto (R1-S8a: si cada archivo está nombrado en un problema, el servicio los revisó a todos y el conteo los cuenta); la clase de
    cada archivo es la de la construcción, no la que lee el módulo."""
    import itertools
    for cortada, (u, i, p, s, n) in itertools.product((False, True), itertools.product(range(4), repeat=5)):
        archivos, no_leidos, revision, clases = _eleccion(u, i, p, s, n, cortada)
        donde = f"usan {u}, ignoran {i}, nombrados en un problema {p}, sin clasificar {s}, no leídos {n}, revisión cortada {cortada}"
        total, impiden = len(archivos) + len(no_leidos), clases.count("impide") + clases.count("sin")
        sin_revisar = bool(revision.problemas) and not revision.usados and not revision.ignorados and "sin" in clases
        texto = carga.texto_del_conteo(archivos, no_leidos, revision)
        assert texto == _conteo_de_referencia(total, clases.count("usa"), clases.count("ignora"), impiden, n, sin_revisar), donde
        cortos = carga.nombres_para_mostrar([ruta for ruta, _ in archivos] + [ruta for ruta, _ in no_leidos])
        tabla = [fila[2] for fila in carga.filas_de_los_archivos(archivos, no_leidos, {ruta: "" for ruta, _ in archivos}, revision, cortos)]
        assert tabla == [TEXTOS_DE_LA_TABLA[clase] for clase in clases] + ["Impide guardar: no se leyó"] * n, donde
        if not sin_revisar:
            numeros = [int(x) for x in re.findall(r"\d+", texto)]
            assert numeros[0] == total == sum(numeros[1:]), donde
            if impiden:
                assert int(re.search(r"(\d+) impiden? guardar", texto).group(1)) == tabla.count(TEXTOS_DE_LA_TABLA["impide"]) + tabla.count(TEXTOS_DE_LA_TABLA["sin"]), donde


# ================================================================================================================================== UM.5, corrección: los hallazgos de la revisión escéptica (11-11)

def _archivos_con_las_cunas(reales, *angulos):
    """Los archivos del campo abierto y los de las cuñas que se piden (el name.data es el de la de 15°)."""
    elegidos = []
    for nombre, ruta in reales.items():
        cuna = re.search(r"Wedge - (\d+)", nombre)
        angulo = int(cuna.group(1)) if cuna else 15 if nombre == "name.data" else None
        if angulo is None or angulo in angulos:
            elegidos.append(ruta)
    return elegidos


def _casillas_de_cuna_a_la_vista(d):
    """Lo que el físico VE como casillas de factor de cuña: las etiquetas «Factor de la cuña de N° ...» visibles y las casillas visibles que no son la de observaciones. Antes deja que Qt destruya lo
    que se soltó (lo hace el bucle de eventos en cuanto vuelve el control, Trampa 9) y que la rejilla se reparta de nuevo."""
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    etiquetas = [w for w in d.findChildren(QLabel) if w.isVisibleTo(d) and w.text().startswith("Factor de la cuña")]
    casillas = [w for w in d.findChildren(QLineEdit) if w.isVisibleTo(d) and w.placeholderText() == "opcional" and w is not d.linea_observaciones]
    return etiquetas, casillas


def _widgets_que_se_montan(d):
    """Los pares de widgets visibles del diálogo (etiquetas, casillas, botones, listas y tablas, sin lo que va dentro de una lista, una tabla o una casilla) cuyos rectángulos se cruzan: en un diálogo
    bien armado no hay ninguno."""
    from PyQt5.QtCore import QPoint, QRect
    from PyQt5.QtWidgets import QAbstractButton, QAbstractItemView, QComboBox, QWidget
    clases = (QLabel, QLineEdit, QAbstractButton, QComboBox, QAbstractItemView)
    hojas = [w for w in d.findChildren(QWidget) if w.isVisibleTo(d) and isinstance(w, clases) and not any(isinstance(p, clases[2:]) for p in _ancestros(w, d))]
    rectangulos = [(w, QRect(w.mapTo(d, QPoint(0, 0)), w.size())) for w in hojas]
    return [(type(a).__name__, getattr(a, "text", lambda: "")(), type(b).__name__, getattr(b, "text", lambda: "")()) for i, (a, ra) in enumerate(rectangulos)
            for b, rb in rectangulos[i + 1:] if ra.intersects(rb)]


def _ancestros(w, hasta):
    p = w.parentWidget()
    while p is not None and p is not hasta:
        yield p
        p = p.parentWidget()


def test_elegir_otra_vez_deja_a_la_vista_solo_las_casillas_de_cuna_de_los_archivos_de_ahora_y_todas_se_leen(bd_vacia, fabrica, elegir, reales, monkeypatch):
    """R1-M1 de la revisión escéptica: cada vez que se eligen archivos, las casillas de factor de cuña que se ven son EXACTAMENTE una por cuña de los archivos de ahora (las de antes salen de la rejilla y
    se destruyen: dejadas a la vista, un factor escrito en ellas no lo leería nadie y se perdería sin aviso), y lo que se escribe en cada casilla visible llega al servicio. (La prueba de arriba que
    elige otra vez solo miraba `campos_wf`: con la rejilla sin limpiar pasaba todos los casos.)"""
    revisiones = espia(monkeypatch, "revisar")
    d = abrir(fabrica())
    for angulos in ((15, 30, 45, 60), (15,), (), (15, 30, 45), (15, 30, 45, 60)):
        elegir(_archivos_con_las_cunas(reales, *angulos))
        QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
        etiquetas, casillas = _casillas_de_cuna_a_la_vista(d)
        assert sorted(e.text() for e in etiquetas) == [f"Factor de la cuña de {a}° en 10 × 10" for a in angulos], angulos
        assert len(casillas) == len(angulos) == d.rejilla_cunas.count() // 2 and sorted(d.campos_wf) == list(angulos), angulos
        assert d.titulo_cunas.isVisibleTo(d) is bool(angulos), angulos
        assert _widgets_que_se_montan(d) == [], angulos                      # lo que se ve no se monta: ni lo de antes sobre lo de ahora, ni una casilla sobre otra
        for angulo in angulos:
            etiqueta, casilla = next(e for e in etiquetas if e.text() == f"Factor de la cuña de {angulo}° en 10 × 10"), d.campos_wf[angulo]
            assert etiqueta.geometry().right() < casilla.geometry().left() and casilla.geometry().top() <= etiqueta.geometry().center().y() <= casilla.geometry().bottom(), angulo
        valores = [f"0.{70 + k}" for k in range(len(casillas))]
        for casilla, valor in zip(casillas, valores):
            casilla.clear()
            QTest.keyClicks(casilla, valor)
        QTest.mouseClick(d.boton_revisar, Qt.LeftButton)
        assert sorted(revisiones[-1][1]["wf_escritos"].values()) == sorted(float(v) for v in valores), angulos          # cada factor escrito en una casilla que se ve llega al servicio


def test_s1_un_fallo_enorme_de_lo_vigente_se_ve_acortado_y_no_ensancha(bd_vacia, fabrica, elegir, reales, monkeypatch):
    """R1-S1 de la revisión escéptica: el texto de lo vigente (el fallo del servicio al saber si ya hay tablas, que puede traer una ruta o un mensaje de la base sin espacios, o un nombre de quien las
    cargó) sale en una etiqueta del diálogo y también va con `sin_palabras_enormes`: no cambia el mínimo del diálogo (con 300 caracteres seguidos pasaba de 959 a 3158 [px])."""
    d, sano = _minimo_tras_revisar(fabrica(), elegir, list(reales.values()))

    def roto(*a, **k):
        raise sqlite3.DatabaseError("database disk image is malformed: " + "q" * 300)
    monkeypatch.setattr(um_datos_haz, "vigente", roto)
    d2, con_el_fallo = _minimo_tras_revisar(fabrica(), elegir, list(reales.values()))
    assert con_el_fallo == sano, f"el mínimo del diálogo pasó de {sano} a {con_el_fallo} [px]"
    assert d2.etiqueta_vigente.text() == "No se pudo saber si ya hay tablas vigentes del Clinac 600, 6 MV: database disk image is malformed: " + "q" * 10 + "…" + "q" * 10
    assert d2.boton_guardar.isEnabled()                    # no saber si hay tablas vigentes no impide revisar ni guardar
    monkeypatch.setattr(um_datos_haz, "vigente", lambda equipo, energia: {"fecha_registro": "2026-11-10 11:00:00", "usuario": "J" * 300})
    d3, con_el_nombre = _minimo_tras_revisar(fabrica(), elegir, list(reales.values()))
    assert con_el_nombre == sano, f"el mínimo del diálogo pasó de {sano} a {con_el_nombre} [px]"
    assert d3.etiqueta_vigente.text().startswith("Ya hay tablas vigentes del Clinac 600, 6 MV, cargadas el 2026-11-10 11:00:00 por " + "J" * 10 + "…" + "J" * 9 + ": al guardar")          # la palabra enorme lleva pegado el «:» y lo cuenta
    assert d3.boton_guardar.isEnabled()


def test_s8_la_revision_que_nombra_a_todos_los_archivos_los_cuenta_y_no_esta_cortada():
    """R1-S8a, capa pura: «sin revisar» es de la revisión que el servicio cortó y dejó archivos sin veredicto. Si TODOS los archivos están nombrados en un problema el servicio los revisó uno por uno
    (cada uno impide guardar, como dice su fila): el conteo los cuenta y suma el total."""
    from services.um_armar import Revision
    a = [("/d/a", b""), ("/d/b", b"")]
    todos = Revision((), (), ("/d/a: la cabecera no dice máquina", "/d/b: la cabecera no dice máquina"), ())
    assert carga.texto_del_conteo(a, [], todos) == "2 archivos: 0 se usan, 0 se ignoran y 2 impiden guardar."
    assert carga.texto_del_conteo(a[:1], [], Revision((), (), ("/d/a: bytes nulos",), ())) == "1 archivo: 0 se usan, 0 se ignoran y 1 impide guardar."       # el único archivo es el que la cortó
    assert carga.texto_del_conteo(a, [("/d/f", "")], todos) == "3 archivos: 0 se usan, 0 se ignoran y 2 impiden guardar; 1 no se pudo leer."
    assert carga.texto_del_conteo(a + [("/d/c", b"")], [], todos) == "3 archivos: sin revisar."          # uno sin veredicto: el servicio no llegó a revisar
    assert carga.texto_del_conteo(a, [], Revision((), (), ("/d/a: bytes nulos",), ())) == "2 archivos: sin revisar."          # nombrado uno y el otro sin veredicto


def test_s8_dos_archivos_que_no_son_de_eclipse_se_cuentan_como_los_dos_que_impiden_guardar(bd_vacia, fabrica, elegir, tmp_path):
    """R1-S8a, por la pantalla y con el servicio real: ninguna cabecera se entiende. El servicio revisa cada archivo y lo nombra en un problema, y la tabla dice «Impide guardar» en cada fila: el
    conteo de arriba no puede decir «sin revisar»."""
    rutas = []
    for nombre in ("uno.txt", "dos.txt"):
        archivo = tmp_path / nombre
        archivo.write_text("# hola\nno es de Eclipse\n", encoding="utf-8")
        rutas.append(str(archivo))
    d = abrir(fabrica())
    d.linea_energia.setText(ENERGIA)
    elegir(rutas)
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    assert d.revision.usados == () and d.revision.ignorados == () and len(d.revision.problemas) == 2         # el servicio no clasificó ninguno... porque los nombró a los dos
    assert [(f[0], f[2]) for f in filas(d.tabla_archivos)] == [("uno.txt", "Impide guardar: vea el motivo"), ("dos.txt", "Impide guardar: vea el motivo")]
    assert d.etiqueta_conteo.text() == "2 archivos: 0 se usan, 0 se ignoran y 2 impiden guardar."
    assert not d.boton_guardar.isEnabled()


CONTEOS_LARGOS = ("24 archivos: 11 se usan y 10 se ignoran; 2 no se pudieron leer.",
                  "24 archivos: 11 se usan, 10 se ignoran y 1 impide guardar; 2 no se pudieron leer.",
                  "22 archivos: 10 se usan, 10 se ignoran y 2 impiden guardar.",
                  "122 archivos: 100 se usan, 10 se ignoran y 10 impiden guardar; 2 no se pudieron leer.")


def test_s8_un_conteo_largo_no_ensancha_el_dialogo_y_se_lee_entero(bd_vacia, fabrica, elegir, reales, tmp_path):
    """R1-S8b de la revisión escéptica: con el texto de UM5-S8 el conteo ya no es corto; sin ajuste de línea fijaba el mínimo del diálogo (de 959 a 1281 [px], más que su tamaño de diseño, con los
    22 reales, un PDD cortado y dos rutas que no existen). Sigue la regla de S1: el mínimo no depende de su texto y un conteo largo se parte en líneas dentro de su celda, entero y sin hacer crecer el
    diálogo; el de siempre sigue en una sola línea."""
    cortar(reales[OPD])
    faltan = [str(tmp_path / "no_existe_1.txt"), str(tmp_path / "no_existe_2.txt")]
    d, ancho = _minimo_tras_revisar(fabrica(), elegir, list(reales.values()) + faltan)
    assert d.etiqueta_conteo.text() == "24 archivos: 11 se usan, 10 se ignoran y 1 impide guardar; 2 no se pudieron leer."          # el caso que midió el revisor
    assert ancho <= carga.TAMANO_DE_LA_CARGA[0] and (d.width(), d.height()) == carga.TAMANO_DE_LA_CARGA
    alto = d.minimumSizeHint().height()
    etiqueta = d.etiqueta_conteo
    for texto in ("",) + CONTEOS_LARGOS + ("22 archivos: 12 se usan y 10 se ignoran.",):
        etiqueta.setText(texto)
        QApplication.processEvents()
        assert (d.minimumSizeHint().width(), d.minimumSizeHint().height()) == (ancho, alto), texto           # lo que dice el conteo no cambia el mínimo del diálogo
        assert etiqueta.heightForWidth(etiqueta.width()) <= etiqueta.height(), texto                         # se lee entero: cabe en el alto de su celda
        assert (d.width(), d.height()) == carga.TAMANO_DE_LA_CARGA, texto
    assert etiqueta.heightForWidth(etiqueta.width()) < 2 * etiqueta.fontMetrics().lineSpacing()         # el de siempre, en una sola línea


def test_el_historial_muestra_el_d0_tal_como_se_guardo(bd_vacia, fabrica, elegir, reales):
    """R1-H1 de la revisión escéptica: el D'0 guardado es el escrito (con todas sus cifras) y el historial, que es el registro de qué se cargó, lo muestra tal cual (`texto_sin_perder`, la misma
    definición que usa «Copiar el desglose»): con `:g` un 0.86012345 salía como «0.860123»."""
    registro = {"fecha_registro": "2026-11-11 10:00:00", "usuario": "Jefa de Física", "activo": 1, "problema": None, "d0_dmax": 0.86012345, "d0_tabla": None, "d0_origen": "medido",
                "archivos": [], "observaciones": None}
    assert carga.filas_del_historial([registro])[0][3] == "0.86012345 [cGy/UM] en dmax (medido)"
    assert carga.filas_del_historial([dict(registro, d0_dmax=None, d0_tabla=1.23456789)])[0][3] == "1.23456789 [cGy/UM] en las condiciones de la tabla (medido)"
    p = fabrica()
    d = abrir(p)
    d.linea_d0.setText("0.86012345")
    d.combo_d0.setCurrentIndex(d.combo_d0.findText(carga.D0_EN_LA_TABLA))
    elegir(list(reales.values()))
    QTest.mouseClick(d.boton_elegir, Qt.LeftButton)
    QTest.mouseClick(d.boton_guardar, Qt.LeftButton)
    assert _sql(bd_vacia, "SELECT d0_dmax, d0_tabla FROM um_datos_haz") == [(None, 0.86012345)]
    QTest.mouseClick(p.boton_historial, Qt.LeftButton)
    assert filas(p.dialogo_historial.tabla)[0][3] == f"0.86012345 [cGy/UM] en las condiciones de la tabla ({carga.ORIGEN_INICIAL})"
