"""F.1: las ayudas de las pruebas del PDF mensual del 600 y del iX con el analisis nuevo (`models/PDF/Mensuales/seccion_placa_mensual.py`, `pelicula_con_recuadro.py`).

Las comparten `test_f1_pdf_mensual_placa.py` (la regla, la capa guardada, lo guardado contra lo recalculado, DA-89) y `test_f1_pelicula_y_guardias.py` (la pelicula con su recuadro, la paginacion y los
guardias por AST). Este archivo NO empieza por `test_`: pytest no lo colecciona.

Todo lo que toca la produccion NUEVA se importa POR PRUEBA (`seccion()`, `recuadro()`...): en HEAD (sin F.1) los archivos de pruebas se coleccionan y cada prueba cae con su error de importacion, no con un error
de coleccion que las tapa a todas (la regla del rojo real).

Reglas que cumple (cada una nacio de un obstaculo ya medido): se siembra TODO con el escritor real del servicio (`svc.guardar`) y con `sqlite3` ANTES de abrir ninguna conexion de QtSql (DP-147: una escritura por
sqlite3 entre aperturas de la conexion Qt rompe el reporte); el PDF sale por el `reporte_mensual` REAL (Trampa 2: `QMessageBox` parchado en la clase y un visor falso); nunca se abre una BD de referencia (la
plantilla se hace una vez con `Conexion()` sobre una ruta temporal parchada ANTES); ningun `lru_cache` (Trampa 10: el mundo sembrado es una fixture de modulo y los PDF se guardan en ese objeto, no en el modulo)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import copy
import importlib
import re
import shutil
import sqlite3

import fitz
import pytest
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import crear_indices

USUARIO = "Fisico de prueba"
CAPAS = ("R", "G", "B")
# Como se dice una capa en una frase con «capa» (el sustantivo es femenino) y como se dice a secas: escritos AQUI a mano, el ancla EXTERNA de `ADJETIVO_DE_LA_CAPA` y `NOMBRE_DE_CAPA`.
CAPA_EN_UNA_FRASE = {"R": "capa roja", "G": "capa verde", "B": "capa azul"}
ESPACIO_DURO = " "

# ----------------------------------------------------------------------------------------------------------------------------------------------- lo que el PDF dice (anclas a mano)
TITULO_DE_LA_SECCION = "Coincidencia del campo luz-radiación (película)"
LINEA_SIN_ANALISIS_NUEVO = "Análisis de la película: pendiente con la herramienta actual (el anterior quedó retirado)"       # DA-89, F1-D-DA89
SIN_DATOS_DEL_ANALISIS_VIEJO = "No hay datos de análisis de imagen"
ENCABEZADO_DE_LA_TABLA_VIEJA = "Análisis de imagen — coordenadas de imagen"
REFERENCIA_TG142 = "TG-142: 2 mm o 1 % por lado; lo evalúa el físico"
LEYENDA_DEL_RECUADRO = "Recuadro: el campo luminoso, entre las cuatro esquinas marcadas en la película"
TITULO_DE_LA_PELICULA = "La película, tal como se guardó"
TITULO_DE_LOS_PARAMETROS = "Parámetros fijos del análisis guardado"
CLAVES_DE_LA_SECCION = ("placa_mensual_valores", "placa_mensual_barrido", "placa_mensual_perfiles", "placa_mensual_pelicula", "placa_mensual_parametros")
# Lo que cada medida guardada se llama en la tabla de valores (rotulo con su unidad entre corchetes): el ancla EXTERNA de `ROTULOS` del modulo.
ROTULOS_ESPERADOS = {"fwhm_crossplane_mm": "FWHM crossplane [mm]", "fwhm_inplane_mm": "FWHM inplane [mm]", "desfase_izquierdo_mm": "Desfase del lado izquierdo [mm]",
                     "desfase_derecho_mm": "Desfase del lado derecho [mm]", "desfase_superior_mm": "Desfase del lado superior [mm]", "desfase_inferior_mm": "Desfase del lado inferior [mm]"}
NO_MEDIBLE = "no medible"
SIMBOLOS_DA18 = "✓✗✔✘⚠❌✅❎☑☒"
COLOR_DEL_RECUADRO_RGB = (0xD8 / 255.0, 0x1B / 255.0, 0x8C / 255.0)                  # el de la pestaña 1 de E.1 (`dibujo_placa_mensual.COLOR_RECUADRO`, «#d81b8c»), escrito aqui a mano
GROSOR_DEL_RECUADRO_PT = 0.5


# ------------------------------------------------------------------------------------------------------------------------------------------------ la produccion, importada por prueba

def seccion():
    return importlib.import_module("models.PDF.Mensuales.seccion_placa_mensual")


def recuadro():
    return importlib.import_module("models.PDF.Mensuales.pelicula_con_recuadro")


def svc():
    return importlib.import_module("services.placa_mensual")


def pm():
    return importlib.import_module("analisisImagenes.placa_mensual")


def pel():
    return importlib.import_module("analisisImagenes.pelicula")


def dibujo():
    return importlib.import_module("analisisImagenes.dibujo_placa_mensual")


def rm():
    """El modulo del reporte mensual (`data.ManejoDatos.load` antes que `models.PDF`: el ciclo de importaciones, como test_r1_r6)."""
    QApplication.instance() or QApplication([])
    import data.ManejoDatos.load  # noqa: F401
    return importlib.import_module("models.PDF.Mensuales.reportes_mensuales")


def pdf_mod():
    rm()
    return importlib.import_module("models.PDF.pdf")


def parametros(base="pixel"):
    """Los parametros de fabrica, todos (una copia). `base`: «pixel» (el valor de pixel normalizado: el rojo de las sinteticas y de las peliculas de 800 UM esta recortado en la densidad optica neta, OD.1) o
    «netOD» (la base por omision del motor)."""
    P = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
    if base == "pixel":
        P["base_de_la_medida"] = pm().BASE_VALOR_DE_PIXEL
    return P


def oraculo(datos, clics, P, modo="automatico"):
    """Lo que el MOTOR da sobre esos bytes y esos clics, por el camino de `guardar` (`leer_pelicula`, `refinar_marca` de cada clic, `analizar`, `barrido`): la verdad contra la que se mira el PDF, que no sale de F.1."""
    pelicula = pel().leer_pelicula(datos)
    tam = pel().escala_mm(pelicula.dpi, P)
    marcas = [pm().refinar_marca(pelicula.gris, c, P, tam, pelicula.validos) for c in clics]
    resultado = pm().analizar(pelicula, marcas, P, modo_piso=modo)
    return resultado, pm().barrido(resultado), marcas


# -------------------------------------------------------------------------------------------------------------------------------------------------------------- el texto de un PDF

def texto_de(pdf):
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        return "\n".join(pagina.get_text() for pagina in doc)
    finally:
        doc.close()


def normal(texto):
    return " ".join(texto.replace(ESPACIO_DURO, " ").split())


def aparece(numero, texto):
    """El numero como palabra aparte, con su signo (que «0.10» no cuente dentro de «0.109», ni «2.30» dentro de «12.301», ni «3.34» dentro de «-3.34»: otra medida con otro signo)."""
    return re.search(rf"(?<![\d.\-+]){re.escape(numero)}(?![\d])", texto) is not None


def n3(valor, con_signo=False):
    """Un numero con tres decimales y nunca '-0.000' (lo que el PDF imprime): escrito aqui aparte, no tomado de F.1."""
    texto = f"{valor:{'+' if con_signo else ''}.3f}"
    return texto.lstrip("+-") if float(texto) == 0 else texto


def paginas_de(pdf, marca):
    """[numero de pagina (desde 1)] de las paginas donde aparece `marca` (con los espacios normalizados)."""
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        return [p.number + 1 for p in doc if normal(marca) in normal(p.get_text())]
    finally:
        doc.close()


def lineas_de(pdf):
    """[linea] del texto del PDF, una por renglon, con los espacios normalizados y sin las vacias."""
    return [normal(l) for l in texto_de(pdf).splitlines() if normal(l)]


def imagenes_de(pdf):
    """[(pagina desde 1, fitz.Rect, xref, ancho_px, alto_px)] de las imagenes embebidas, en el orden del flujo de la pagina."""
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        return [(p.number + 1, fitz.Rect(i["bbox"]), i["xref"], i["width"], i["height"]) for p in doc for i in p.get_image_info(xrefs=True)]
    finally:
        doc.close()


# ------------------------------------------------------------------------------------------------------------------------------------------------------------- la BD y el mundo sembrado

@pytest.fixture(scope="module")
def app():
    """La QApplication, con una referencia viva todo el modulo: `QApplication.instance() or QApplication([])` a secas la deja sin dueno y el recolector la destruye (el siguiente `QPixmap` aborta el proceso)."""
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    """La BD nueva con todo el esquema y los indices unicos (los del contrato de QC), hecha UNA vez, con el usuario de la siembra; cada modulo trabaja sobre su copia. Nunca se abre una BD de referencia."""
    ruta = str(tmp_path_factory.mktemp("f1") / "plantilla.db")
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
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO users (user, fullname, role) VALUES ('fp', ?, 'Fisico Medico')", (USUARIO,))
    con.commit()
    con.close()
    return ruta


def generar_pdf(ruta, fecha, maquina, mp):
    """`(bytes del PDF | None, [avisos de error])` del `reporte_mensual` REAL (sin abrir el visor). El reporte se traga los errores en un `QMessageBox.critical`: aqui se capturan, no se ocultan.
    `mp`: un `MonkeyPatch` (el de la prueba o el del mundo) que parcha el cuadro de dialogo, el visor y nada mas."""
    errores, captura = [], {}
    mp.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: errores.append(a)))
    for aviso in ("information", "warning"):
        mp.setattr(QMessageBox, aviso, staticmethod(lambda *a, **k: None))

    class FalsoVisor:
        def __init__(self, pdf_data=None, **k):
            captura["pdf"] = pdf_data

        def show(self):
            pass

    class Pantalla:
        def opeenDatabase(self):
            if QSqlDatabase.contains("qt_sql_default_connection"):
                QSqlDatabase.removeDatabase("qt_sql_default_connection")
            db = QSqlDatabase.addDatabase("QSQLITE")
            db.setDatabaseName(ruta)
            db.open()
            return db

    modulo = rm()
    mp.setattr(modulo, "PdfViewer", FalsoVisor)
    modulo.reporte_mensual(Pantalla(), fecha, maquina, "IDC", "Control Mensual", {}, None, "")
    return (bytes(captura["pdf"]) if "pdf" in captura else None), errores


class Mundo:
    """Una BD sembrada con tantos controles mensuales como escenarios (cada uno de un mes distinto: el indice unico de `controles` es por equipo, tipo y mes) y los PDF que de ella salen (se generan al
    pedirlos y se guardan en este objeto). Se siembra todo antes de abrir QtSql."""

    def __init__(self, ruta, mp):
        self.ruta = ruta
        self._mp = mp
        self._n = 0
        self.refs, self.fechas, self.maquinas = {}, {}, {}
        self._pdfs, self._errores = {}, {}

    def sql(self, sentencia, parametros=()):
        con = sqlite3.connect(self.ruta)
        try:
            cursor = con.execute(sentencia, parametros)
            con.commit()
            return cursor.lastrowid
        finally:
            con.close()

    def consulta(self, sentencia, parametros=()):
        con = sqlite3.connect(self.ruta)
        try:
            return con.execute(sentencia, parametros).fetchall()
        finally:
            con.close()

    def control(self, nombre, maquina="Clinac 600", fila_preguntas=True, imagen=None, franjas=False):
        """Un control mensual: su fila de `preguntas` (con la imagen vieja, si `imagen`) y, si `franjas`, dos franjas vigentes del analisis VIEJO con valores que no se parecen a ninguno del nuevo."""
        self._n += 1
        fecha = f"15/{1 + self._n % 12:02d}/{2010 + self._n // 12}"
        ref = self.sql("INSERT INTO controles (equipo, control, fecha, user_id) VALUES (?, 'Mensual', ?, ?)", (maquina, fecha, USUARIO))
        if fila_preguntas:
            self.sql("INSERT INTO preguntas (ref, iso_mec, imagen) VALUES (?, '0.5', ?)", (ref, imagen))
        if franjas:
            for franja, base in (("Franja 1", 77.0), ("Franja 2", 88.0)):
                self.sql("INSERT INTO analisis_placa_franjas (ref, franja, ancho_media_h, ancho_media_v, penumbra_izq_h, penumbra_izq_v, penumbra_der_h, penumbra_der_v, "
                         "diferencia_arriba_izq, diferencia_arriba_der, diferencia_abajo_izq, diferencia_abajo_der) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (ref, franja, base + 0.7771, base + 0.8882, base + 0.1113, base + 0.2224, base + 0.3335, base + 0.4446, base + 0.5557, base + 0.6668, base + 0.7779, base + 0.9991))
        self.refs[nombre], self.fechas[nombre], self.maquinas[nombre] = ref, fecha, maquina
        return ref

    def guardar(self, nombre, datos, clics, capa, parametros_=None, modo="automatico", archivo="placa.jpeg"):
        """Guarda el analisis nuevo del control `nombre` con el ESCRITOR REAL del servicio."""
        return svc().guardar(self.refs[nombre], USUARIO, datos, archivo, clics, parametros_ if parametros_ is not None else parametros(), capa, modo)

    def pdf(self, nombre):
        """Los bytes del PDF del control `nombre` (por el reporte real). Si el reporte avisa de un error, la prueba que lo pide falla con el aviso."""
        if nombre not in self._pdfs:
            pdf, errores = generar_pdf(self.ruta, self.fechas[nombre], self.maquinas[nombre], self._mp)
            self._errores[nombre] = errores
            if pdf is None or errores:
                raise AssertionError(f"el reporte de {nombre!r} ({self.maquinas[nombre]}, {self.fechas[nombre]}) avisó de un error: {errores}")
            self._pdfs[nombre] = pdf
        return self._pdfs[nombre]


def mundo_nuevo(plantilla, tmp_path_factory):
    """(Mundo, MonkeyPatch abierto, Conexion previa): una copia de la plantilla con `ruta_base_datos` parchada y un `Conexion` sin arranque (el esquema ya esta). El que llama cierra el parche."""
    ruta = str(tmp_path_factory.mktemp("f1mundo") / "mundo.db")
    shutil.copy(plantilla, ruta)
    mp = pytest.MonkeyPatch()
    mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    previo = Conexion._instance
    Conexion._instance = object.__new__(Conexion)
    return Mundo(ruta, mp), mp, previo


def cerrar_mundo(mp, previo):
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.removeDatabase("qt_sql_default_connection")
    Conexion._instance = previo
    mp.undo()
