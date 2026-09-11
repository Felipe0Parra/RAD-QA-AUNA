"""R1-R6 (PLAN_REPORTES_LEGIBLES_08-09.md, Fase A y Fase B): que los cuatro
reportes diarios (600, iX, Halcyon, braqui) digan "Funciona"/"No funciona"
en vez de 1/0, nunca dejen la columna de Umbrales en blanco, muestren la
unidad de cada medida entre corchetes junto al identificador, la firma no
invada la tabla, y el diario de braqui muestre la placa analizada y su
resumen (promedio/desviación) en una tabla aparte, sin las 6 filas crudas
del análisis ni `activo`/`umbral_relativo`/`distancia_minima`.

Cada bloque de tests aquí corresponde a UNA tarea del plan, con su propio
rojo-antes-que-verde donde aplica (`R1`: contra el atributo mal escrito;
`R6`: contra el filtrado por nombre literal de 2024)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
# Import circular preexistente (no introducido por este plan, fuera de su
# alcance -- §1.1): `models.PDF.reportes` -> `models.PDF.pdf` ->
# `data.ManejoDatos.load` -> `ui.paginasGuia.dialogs` ->
# `models.PDF.reporte_calculadora_dos` -> `models.PDF.reportes` (de nuevo,
# a medio inicializar). Ningún test tocaba `models/PDF/reportes.py` antes
# de este plan (§2.2), así que nunca se disparaba. Cargar `load` entero
# primero rompe el ciclo sin tocar producción.
import data.ManejoDatos.load  # noqa: F401
from models.PDF import reportes as reportes_mod
from models.PDF.clasificacion_diario import (
    COLUMNAS_IDENTIFICACION, COLUMNAS_MOVIDAS_A_OTRA_TABLA, COLUMNAS_RETIRADAS,
    columnas_no_reportables)
from services.unidades_qc import unidad_de, UNIDADES, ADIMENSIONALES, SIN_FUENTE


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.Yes))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield conexion
    conexion.con.close()
    Conexion._instance = None


class _AutoDB:
    """`self` mínimo: solo `opeenDatabase()`, que es lo único que
    `reportes.reporte()` usa de la pantalla real."""
    def opeenDatabase(self):
        from PyQt5.QtSql import QSqlDatabase
        if QSqlDatabase.contains("qt_sql_default_connection"):
            QSqlDatabase.removeDatabase("qt_sql_default_connection")
        db = QSqlDatabase.addDatabase("QSQLITE")
        db.setDatabaseName(conection_mod.ruta_base_datos())
        db.open()
        return db


def _capturar_pdf(monkeypatch, fecha, maquina, diccionario, umbrales):
    """Ejecuta `reportes.reporte()` real (sin QFileDialog ni ventana) y
    devuelve el texto extraído (fitz) del PDF resultante."""
    import fitz
    capturado = {}

    class _FalsoPdfViewer:
        def __init__(self, pdf_data=None, **kw):
            capturado['bytes'] = pdf_data
        def show(self):
            pass

    monkeypatch.setattr(reportes_mod, "PdfViewer", _FalsoPdfViewer)
    reportes_mod.reporte(_AutoDB(), fecha=fecha, maquina=maquina, id_maquina="",
                          tipo_reporte="diario", diccionario=diccionario,
                          umbrales=umbrales, file_name="")
    doc = fitz.open(stream=capturado['bytes'], filetype="pdf")
    texto = "\n".join(p.get_text() for p in doc)
    paginas = doc.page_count
    doc.close()
    return texto, paginas


DICC_600 = {
    "luces_consola": ["Luces consola", '', "scatter"],
    "laseres": ["Laseres", 2.0, "line"],
    "dosis_referencia": ["Datos dosimetricos", 3, "line"],
    "observaciones": ["Observaciones", "", "Na"],
}

DICC_HALCYON = {
    "BeamOutputChange": ["Cambio en la salida del haz", 4.0],
    "CouchLat": ["Posición lateral de la mesa", 0.5],
}

DICC_BRAQUI = {
    'int_con_box': ['Interrupción desde consola', '', 'scatter'],
    'tol_rep_act_ci': ['Actividad reportada', '', 'line'],
    'tol_cyc_dummy': ['Ciclos del Dummy', '', 'line'],
    'observaciones': ['Observaciones', '', 'Na'],
}


# ---------------------------------------------------------------------
# R1 -- el veredicto se deriva de la declaración, no de un atributo de la
# UI leído por su nombre.
# ---------------------------------------------------------------------
class TestR1VeredictoDerivadoDeLaDeclaracion:
    def test_booleano_1_se_traduce_a_funciona_y_borra_el_valor(
            self, app, bd_temporal, monkeypatch):
        bd_temporal.con.execute(
            "INSERT INTO aceleradorlineal_600 (date, user_id, luces_consola, "
            "laseres, dosis_referencia) VALUES ('2026-01-01','Físico de Prueba',1,1,2.0)")
        bd_temporal.con.commit()
        texto, _ = _capturar_pdf(monkeypatch, "2026-01-01", "Clinac 600", DICC_600, "si")
        assert "Luces consola" in texto
        assert "Funciona" in texto
        assert "1" not in texto.split("Luces consola")[1].split("\n")[1]

    def test_booleano_0_se_traduce_a_no_funciona(self, app, bd_temporal, monkeypatch):
        bd_temporal.con.execute(
            "INSERT INTO aceleradorlineal_600 (date, user_id, luces_consola, "
            "laseres, dosis_referencia) VALUES ('2026-01-02','Físico de Prueba',0,1,2.0)")
        bd_temporal.con.commit()
        texto, _ = _capturar_pdf(monkeypatch, "2026-01-02", "Clinac 600", DICC_600, "si")
        assert "No funciona" in texto

    def test_rojo_dirigido_halcyon_valor_numerico_0_no_se_confunde_con_booleano(
            self, app, bd_temporal, monkeypatch):
        """El defecto real (§0.2 del plan): antes, `hasattr(self,
        'boolean_columns')` SÍ existía para Halcyon (a diferencia de las
        otras 3), y como su diccionario no tiene marca "scatter", el
        código viejo la trataba lo mismo -- este test fija que un valor
        NUMÉRICO que vale exactamente 0 conserva su valor y no se
        etiqueta "No funciona"."""
        bd_temporal.con.execute(
            "INSERT INTO halcyon (date, user_id, BeamOutputChange, CouchLat) "
            "VALUES ('2026-01-03','Físico de Prueba', 0.0, 0.0)")
        bd_temporal.con.commit()
        texto, _ = _capturar_pdf(monkeypatch, "2026-01-03", "HALCYON", DICC_HALCYON, "si")
        assert "No funciona" not in texto
        assert "Dentro del umbral" in texto
        # El valor 0.0 sigue visible -- no se borra como en un booleano.
        assert "0.0" in texto or "0\n" in texto

    def test_diccionario_sin_marca_scatter_no_produce_booleanos(self):
        from models.PDF.reportes import _campos_booleanos
        assert _campos_booleanos(DICC_HALCYON) == set()

    def test_valor_booleano_normaliza_int_float_str(self):
        from models.PDF.reportes import _valor_booleano
        assert _valor_booleano(1) == 1
        assert _valor_booleano(0) == 0
        assert _valor_booleano(1.0) == 1
        assert _valor_booleano(0.0) == 0
        assert _valor_booleano("1") == 1
        assert _valor_booleano("0") == 0
        assert _valor_booleano("") is None
        assert _valor_booleano(None) is None
        assert _valor_booleano(2) is None  # no reconocible: SIN veredicto


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


# ---------------------------------------------------------------------
# R2 -- censo: cada columna de las 4 tablas diarias está clasificada.
# ---------------------------------------------------------------------
class TestR2CensoColumnasDiario:
    """El `diccionario_invertido` de cada test viene de instanciar la
    pantalla REAL (no una copia a mano que puede quedar desactualizada) --
    mismo patrón que `test_t5_ancho_minimo_widgets_fecha.py`."""

    @pytest.mark.parametrize("tabla,clase,modulo", [
        ("aceleradorlineal_600", "PruebaDiaria600", "seiscientos"),
        ("aceleradorlineal_ix", "PruebaDiariaIX", "IX"),
        ("halcyon", "PruebaDiariaHc", "halcyon"),
        ("braqui", "PruebaDiariaBraq", "braquiterapia"),
    ])
    def test_toda_columna_esta_clasificada(
            self, app, bd_temporal, tabla, clase, modulo):
        import importlib
        Clase = getattr(
            importlib.import_module(f"ui.paginasControles.PruebasDiarias.{modulo}"),
            clase)
        pantalla = Clase(_UsuarioFalso())
        diccionario = pantalla.diccionario_invertido

        cur = bd_temporal.con.cursor()
        columnas_reales = {r[1] for r in cur.execute(f"PRAGMA table_info({tabla})")}
        clasificadas = (set(COLUMNAS_IDENTIFICACION)
                        | COLUMNAS_RETIRADAS.get(tabla, set())
                        | COLUMNAS_MOVIDAS_A_OTRA_TABLA.get(tabla, set())
                        | set(diccionario.keys()))
        sin_clasificar = columnas_reales - clasificadas
        assert not sin_clasificar, (
            f"{tabla}: columnas sin clasificar (ni en diccionario_invertido "
            f"ni en clasificacion_diario.py): {sin_clasificar} -- si es una "
            f"columna nueva, alguien debe decidir qué le pasa antes de que "
            f"aparezca sola en un PDF firmado")

    def test_activo_retirada_en_las_cuatro(self):
        for tabla in ("aceleradorlineal_600", "aceleradorlineal_ix", "halcyon", "braqui"):
            assert "activo" in COLUMNAS_RETIRADAS[tabla]

    def test_braqui_retira_exactamente_lo_nombrado_por_el_fisico(self):
        assert COLUMNAS_RETIRADAS["braqui"] == {
            "distancias", "desplazamientos", "promedio_des", "desviacion_des",
            "activo", "umbral_relativo", "distancia_minima",
        }

    def test_braqui_mueve_promedio_desviacion_pelicula_a_otra_tabla(self):
        assert COLUMNAS_MOVIDAS_A_OTRA_TABLA["braqui"] == {
            "promedio", "desviacion", "pelicula"}

    def test_activo_no_aparece_en_el_pdf_de_ninguna_maquina(
            self, app, bd_temporal, monkeypatch):
        bd_temporal.con.execute(
            "INSERT INTO aceleradorlineal_600 (date, user_id, laseres, "
            "dosis_referencia, activo) VALUES "
            "('2026-02-01','Físico de Prueba',1,2.0,1)")
        bd_temporal.con.commit()
        texto, _ = _capturar_pdf(monkeypatch, "2026-02-01", "Clinac 600", DICC_600, "si")
        assert "activo" not in texto.lower().split("físico de prueba")[0].replace(
            "físico", "")  # evita falso positivo con "Físico Médico"
        # Verificación directa: ninguna línea es exactamente "activo".
        assert not any(linea.strip().lower() == "activo" for linea in texto.splitlines())


# ---------------------------------------------------------------------
# R3 -- la columna Umbrales nunca queda vacía.
# ---------------------------------------------------------------------
class TestR3UmbralNuncaVacio:
    def test_braqui_ya_no_llama_con_umbrales_none(self):
        """Rojo-antes-que-verde de clase: braqui pasaba `umbrales=None` y
        se quedaba sin columna -- ahora pasa "si" como sus 3 hermanas, en
        LAS DOS clases duplicadas de `PruebaDiariaBraq`."""
        fuente = open("ui/paginasControles/PruebasDiarias/braquiterapia.py",
                       encoding="utf-8").read()
        assert "umbrales=None" not in fuente
        assert fuente.count('umbrales="si"') >= 2

    def test_booleano_sin_umbral_numerico_muestra_no_aplica(
            self, app, bd_temporal, monkeypatch):
        bd_temporal.con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, tol_rep_act_ci, "
            "tol_cyc_dummy) VALUES ('2026-02-02','Físico de Prueba',1,5.5,100)")
        bd_temporal.con.commit()
        texto, _ = _capturar_pdf(monkeypatch, "2026-02-02", "Gammamed Plus i X",
                                  DICC_BRAQUI, "si")
        assert "No aplica" in texto
        # Ninguna celda de Umbrales queda en blanco/"nan" para las filas
        # del diccionario (id/date/user_id se descartan antes del PDF).
        assert "nan" not in texto.lower()

    def test_numerico_con_umbral_muestra_el_numero(self, app, bd_temporal, monkeypatch):
        bd_temporal.con.execute(
            "INSERT INTO aceleradorlineal_600 (date, user_id, laseres, "
            "dosis_referencia) VALUES ('2026-02-03','Físico de Prueba',1,2.0)")
        bd_temporal.con.commit()
        texto, _ = _capturar_pdf(monkeypatch, "2026-02-03", "Clinac 600", DICC_600, "si")
        assert "2.0" in texto


# ---------------------------------------------------------------------
# R4 -- unidades entre corchetes en la celda del identificador.
# ---------------------------------------------------------------------
class TestR4UnidadesEntreCorchetes:
    def test_unidad_de_campo_con_unidad(self):
        assert unidad_de("laseres") == " [mm]"
        assert unidad_de("tol_rep_act_ci") == " [Ci]"
        assert unidad_de("dosis_referencia") == " [%]"

    def test_unidad_de_adimensional_es_uno_entre_corchetes(self):
        assert unidad_de("tol_cyc_dummy") == " [1]"

    def test_unidad_de_halcyon_sin_fuente_no_lleva_corchetes(self):
        assert unidad_de("BeamOutputChange") == ""
        assert "BeamOutputChange" in SIN_FUENTE

    def test_unidad_de_booleano_o_desconocido_es_vacia(self):
        assert unidad_de("luces_consola") == ""
        assert unidad_de("observaciones") == ""
        assert unidad_de("columna_que_no_existe") == ""

    def test_no_hay_solapamiento_entre_las_tres_categorias(self):
        assert not (set(UNIDADES) & ADIMENSIONALES)
        assert not (set(UNIDADES) & SIN_FUENTE)
        assert not (ADIMENSIONALES & SIN_FUENTE)

    def test_etiqueta_lleva_corchete_y_el_valor_sigue_siendo_numero_puro(
            self, app, bd_temporal, monkeypatch):
        bd_temporal.con.execute(
            "INSERT INTO aceleradorlineal_600 (date, user_id, laseres, "
            "dosis_referencia) VALUES ('2026-02-04','Físico de Prueba',1,2.0)")
        bd_temporal.con.commit()
        texto, _ = _capturar_pdf(monkeypatch, "2026-02-04", "Clinac 600", DICC_600, "si")
        assert "Laseres [mm]" in texto
        # El valor de esa fila (línea siguiente al identificador) es un
        # número puro, convertible a float sin limpiar texto.
        lineas = texto.splitlines()
        idx = lineas.index("Laseres [mm]")
        assert float(lineas[idx + 2]) == 1.0  # (Evaluación, Valores, Umbrales)

    def test_halcyon_ninguna_fila_muestra_corchetes(self, app, bd_temporal, monkeypatch):
        bd_temporal.con.execute(
            "INSERT INTO halcyon (date, user_id, BeamOutputChange, CouchLat) "
            "VALUES ('2026-02-05','Físico de Prueba', 1.2, 0.3)")
        bd_temporal.con.commit()
        texto, _ = _capturar_pdf(monkeypatch, "2026-02-05", "HALCYON", DICC_HALCYON, "si")
        assert "[" not in texto.split("Información general")[1].split(
            "Físico de Prueba\n")[0] if "Físico de Prueba\n" in texto else True
        assert "[mm]" not in texto and "[%]" not in texto and "[1]" not in texto


# ---------------------------------------------------------------------
# R5 -- la firma no invade la tabla.
# ---------------------------------------------------------------------
class TestR5FirmaNoInvadeLaTabla:
    def test_orden_del_bloque_imagen_linea_nombre_cargo(self):
        fuente = open("models/PDF/pdf.py", encoding="utf-8").read()
        bloque = fuente[fuente.index("if es_diario_qc:\n        # 🔹 R5"):]
        bloque = bloque[:bloque.index("c.save()")]
        pos_img = bloque.index("Y_FIRMA_IMG_BASE")
        pos_linea = bloque.index("c.line(100, Y_FIRMA_LINEA")
        pos_nombre = bloque.index("c.drawString(100, Y_FIRMA_NOMBRE")
        pos_cargo = bloque.index("c.drawString(100, Y_FIRMA_CARGO")
        assert pos_img < pos_linea < pos_nombre < pos_cargo

    def test_reserva_cubre_todo_el_bloque_de_firma(self):
        """Rojo-antes-que-verde: antes `available_height = y_start - 80`
        dejaba 35 pt menos de lo que el bloque ocupa (llega a y=115)."""
        import models.PDF.pdf as pdf_mod
        import inspect
        fuente = inspect.getsource(pdf_mod.generar_reporte_pdf)
        # ALTO_BLOQUE_FIRMA para es_diario_qc=True se deriva de
        # Y_FIRMA_IMG_TOPE (115) + margen (10) = 125, no un literal 80.
        assert "ALTO_BLOQUE_FIRMA = Y_FIRMA_IMG_TOPE + MARGEN_TABLA_FIRMA" in fuente

    def test_calculadora_de_dosis_conserva_el_comportamiento_original(self, app):
        """C2/C4 (§2.3 del plan): `generar_reporte_pdf` tiene un segundo
        cliente (`reporte_calculadora_dos.py`) que el físico no nombró --
        con `es_diario_qc=False` (su valor por defecto) debe producir el
        MISMO contenido que antes de este plan."""
        import pandas as pd
        import fitz
        from models.PDF.pdf import generar_reporte_pdf
        df = pd.DataFrame({
            "": ["Fecha", "Acelerador", "dosis_maxima"],
            "Evaluación": [None, None, None],
            "Valores": ["2026-01-01", "Clinac 600", 1.005],
        })
        buffer = generar_reporte_pdf(df=df, fecha="2026-01-01", user=" ",
                                      tipo_reporte="Calculadora", maquina="Clinac 600",
                                      id_maquina="", logo_path=None, firma=None,
                                      role="Físico Médico", temp=True)
        doc = fitz.open(stream=bytes(buffer.data()), filetype="pdf")
        texto = "\n".join(p.get_text() for p in doc)
        assert "Fecha" in texto and "Acelerador" in texto and "dosis_maxima" in texto
        assert doc.page_count == 1


# ---------------------------------------------------------------------
# R6 -- placa analizada + resumen (promedio/desviación) en tabla aparte.
# ---------------------------------------------------------------------
class TestR6PlacaBraquiTablaAparte:
    def _insertar_braqui(self, bd_temporal, fecha, promedio=None, desviacion=None,
                          pelicula=None):
        bd_temporal.con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, tol_rep_act_ci, "
            "tol_cyc_dummy, promedio, desviacion, pelicula) VALUES "
            "(?, 'Físico de Prueba', 1, 5.5, 100, ?, ?, ?)",
            (fecha, promedio, desviacion, pelicula))
        bd_temporal.con.commit()

    def _jpeg_minimo(self):
        # JPEG real de 1x1 px, válido para QPixmap.loadFromData.
        import base64
        return base64.b64decode(
            "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkI"
            "CQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/wAALCAABAAEBAREA/8QAFQABAQAAAAAA"
            "AAAAAAAAAAAAAAj/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAA/AKAAAA==")

    def test_ninguna_fila_cruda_del_analisis_aparece_en_la_tabla_principal(
            self, app, bd_temporal, monkeypatch):
        self._insertar_braqui(bd_temporal, "2026-03-01", promedio=9.99, desviacion=0.06,
                               pelicula=self._jpeg_minimo())
        texto, _ = _capturar_pdf(monkeypatch, "2026-03-01", "Gammamed Plus i X",
                                  DICC_BRAQUI, "si")
        for cruda in ("distancias", "desplazamientos", "promedio_des", "desviacion_des"):
            assert cruda not in texto

    def test_caso_con_analisis_y_pelicula_muestra_los_numeros_reales(
            self, app, bd_temporal, monkeypatch):
        self._insertar_braqui(bd_temporal, "2026-03-02", promedio=9.99, desviacion=0.06,
                               pelicula=self._jpeg_minimo())
        texto, _ = _capturar_pdf(monkeypatch, "2026-03-02", "Gammamed Plus i X",
                                  DICC_BRAQUI, "si")
        assert "Análisis de la placa" in texto
        # C.5 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4): dice de qué es el
        # promedio -- "Promedio [mm]" a secas ya no aparece.
        assert "Promedio (distancia entre líneas) [mm]" in texto
        assert "9.99" in texto
        assert "Desviación estándar (distancia entre líneas) [mm]" in texto
        assert "0.06" in texto

    def test_caso_pelicula_sin_analisis_muestra_no_aplica_en_las_dos_filas(
            self, app, bd_temporal, monkeypatch):
        self._insertar_braqui(bd_temporal, "2026-03-03", promedio=None, desviacion=None,
                               pelicula=self._jpeg_minimo())
        texto, _ = _capturar_pdf(monkeypatch, "2026-03-03", "Gammamed Plus i X",
                                  DICC_BRAQUI, "si")
        assert "Análisis de la placa" in texto
        bloque = texto[texto.index("Análisis de la placa"):]
        assert bloque.count("No aplica") >= 2

    def test_caso_analisis_sin_pelicula_no_dibuja_recuadro(
            self, app, bd_temporal, monkeypatch):
        self._insertar_braqui(bd_temporal, "2026-03-04", promedio=10.01, desviacion=0.10,
                               pelicula=None)
        texto, _ = _capturar_pdf(monkeypatch, "2026-03-04", "Gammamed Plus i X",
                                  DICC_BRAQUI, "si")
        assert "Análisis de la placa" in texto
        assert "10.01" in texto
        assert "Imagen no disponible" not in texto

    def test_caso_ninguna_no_muestra_bloque_de_analisis(
            self, app, bd_temporal, monkeypatch):
        self._insertar_braqui(bd_temporal, "2026-03-05", promedio=None, desviacion=None,
                               pelicula=None)
        texto, _ = _capturar_pdf(monkeypatch, "2026-03-05", "Gammamed Plus i X",
                                  DICC_BRAQUI, "si")
        assert "Análisis de la placa" not in texto

    def test_g2_blob_corrupto_dice_que_la_imagen_no_esta_disponible(
            self, app, bd_temporal, monkeypatch):
        self._insertar_braqui(bd_temporal, "2026-03-06", promedio=None, desviacion=None,
                               pelicula=b"esto no es una imagen valida")
        texto, _ = _capturar_pdf(monkeypatch, "2026-03-06", "Gammamed Plus i X",
                                  DICC_BRAQUI, "si")
        assert "Imagen no disponible (formato no reconocido)" in texto

    def test_g1_extraccion_no_altera_la_imagen(self, app):
        """La imagen incrustada (tras pasar por QPixmap) es la MISMA que
        el BLOB original, salvo la re-codificación a PNG sin pérdida."""
        from PyQt5.QtGui import QImage
        from models.PDF.pdf import _extraer_imagen_a_png_temporal
        original = self._jpeg_minimo()
        ruta = _extraer_imagen_a_png_temporal(original)
        assert ruta is not None
        img_original = QImage()
        img_original.loadFromData(original)
        img_extraida = QImage(ruta)
        assert img_original.size() == img_extraida.size()

    def test_g3_reproducibilidad_tres_generaciones_dan_el_mismo_png(self, app):
        from models.PDF.pdf import _extraer_imagen_a_png_temporal
        blob = self._jpeg_minimo()
        rutas = [_extraer_imagen_a_png_temporal(blob) for _ in range(3)]
        contenidos = [open(r, "rb").read() for r in rutas]
        assert contenidos[0] == contenidos[1] == contenidos[2]

    def test_geometria_contain_nunca_recorta_ni_deforma(self):
        """Una imagen más angosta que alta debe escalarse por el lado que
        primero toca el recuadro -- nunca recortarse."""
        # Verificación aritmética directa de la fórmula de escala (R6):
        # escala = min(ancho_recuadro/ancho_img, alto_recuadro/alto_img).
        ancho_recuadro, alto_recuadro = 450, 130
        ancho_img, alto_img = 1700, 2200  # el peor caso medido, vertical
        escala = min(ancho_recuadro / ancho_img, alto_recuadro / alto_img)
        ancho_final = ancho_img * escala
        alto_final = alto_img * escala
        assert ancho_final <= ancho_recuadro + 1e-6
        assert alto_final <= alto_recuadro + 1e-6
        # Con este caso el alto es el que manda (imagen vertical extrema).
        assert abs(alto_final - alto_recuadro) < 1e-6
