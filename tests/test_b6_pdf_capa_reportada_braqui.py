"""B.6 (PLAN_ANALISIS_PELICULAS_08-10.md, DP-157, DA-83/DA-85, decision de Opus `borradores/B6/decision_figura_pdf_Opus.md`): los DOS PDF de la posicion
inicial de braquiterapia (el DIARIO, debajo de R6, y el MENSUAL, la fila «Desplazamiento inicial (mm)» y una seccion propia) salen de la CAPA QUE GUARDO EL
REGISTRO (la elegida en el menu, B.7; por omision la verde): su nombre, sus valores, sus medidas estadisticas guardadas y su perfil, sin mezclar capas.

Lo que se garantiza, cada cosa con su prueba (el rojo contra HEAD esta en el anexo: logs/B6/rojo.log):
  - DE PUNTA A PUNTA (la prueba que PARAMETRIZA sobre la capa guardada, R, G y B sobre EPSON009, donde las tres se miden): el PDF del diario y el del mensual,
    generados por `reportes.reporte()` y `reporte_mensual()` reales sobre una prueba sembrada con el ESCRITOR REAL del servicio, dicen el nombre y los numeros de ESA
    capa y ninguno de otra (ni el gris ni las otras dos), y llevan UNA figura de 420 x 400 pt que es la de esa capa;
  - un registro sin capa (anterior a B.5, o guardado por la pagina de antes de B.7, B6-F4) se imprime como hoy, con el gris, y el bloque lo dice; cambiar `CAPA_POR_OMISION` no
    cambia ningun PDF (ningun PDF la lee);
  - la figura se dibuja SOLO si la version del algoritmo guardada es la de hoy (si no, ni se reconstruye: cero llamadas a `analizar`) y si volver a medir da las medidas
    guardadas de esa capa (px a 0.01, mm a 0.01 x escala, estado y filas exactos); lo impreso es SIEMPRE lo guardado; un fallo al reconstruir o dibujar no tumba el PDF: sale
    con lo guardado, la fila «Perfil» lo dice sin texto tecnico y el detalle va a `error_log.txt`;
  - paginacion: el bloque del diario es una unidad (su tabla y su figura salen juntas), salta entero a la pagina siguiente si no cabe y nunca invade la franja de la firma,
    de 0 a 70 filas de la tabla y en los tres casos de R6; el mensual sale sin `LayoutError` en los tres tipos de calibracion y la seccion va tras «Condiciones de medicion»;
  - PD1: cada entrada de `TRAZO_DE_PARAMETRO` esta en la figura del PDF (un artista, el eje en mm, el pie con su valor, «tolerancia» en la linea y la resolucion del escaneo
    en su fila);
  - capas: ninguna capa escrita a mano en el servicio, en `reportes.py`, en `pdf.py`, en `reportes_mensuales.py` ni en el modulo del PDF, y ningun PDF lee `CAPA_POR_OMISION`;
    el modulo de dibujo (mudado de la pagina con el cuerpo igual) no importa Qt ni matplotlib, el del PDF no importa el motor, Qt ni `pyplot`, y el servicio no dibuja;
  - REVISION DE LA RONDA 1 (corrector, 17-10): (R1-PROD-01) el nombre de la capa CONCUERDA con la palabra «capa» en la linea, en la fila y en el titulo de la figura («Capa roja», no «Capa rojo»): lo
    esperado esta escrito aqui y no sale de una constante del codigo, la tabla de los COLORES (`NOMBRE_DE_CAPA`: rojo, verde, azul; para los menus) no arma ninguna frase con «capa» en TODO el
    codigo de produccion y la que concuerda (`ADJETIVO_DE_LA_CAPA`) es una sola; (R1P-01) la linea conserva el nombre de su capa tambien sin el cambio de fuente (la llamada de la tabla de registros);
    (R1P-02) el detalle de por que no se dibuja el perfil (las medidas que no salen) queda en `error_log.txt`; (R1P-03) cada perfil lee sus siete columnas y ninguna de otro perfil: se prueba el
    COMPORTAMIENTO, no la forma de escribir el codigo (un refactor equivalente no debe romper ninguna prueba).
Se siembra TODO antes de abrir ninguna conexion de Qt (una escritura por sqlite3 entre aperturas de la conexion Qt rompe el reporte: DP-147)."""
import gc
import io
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pytest
from PIL import Image
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QMessageBox

import data.ManejoDatos.conection as conection_mod  # noqa: F401
import data.ManejoDatos.load  # noqa: F401  (antes que models.PDF: el ciclo de importaciones, como test_r1_r6)
from analisisImagenes import posicion_inicial_braqui as motor
from analisisImagenes.pelicula import CAPAS
from models.PDF import reportes as reportes_mod
from services import posicion_inicial_braqui as svc
from test_pi1_motor_posicion_inicial import CLICS_EPSON009, CLICS_PLACA_REAL
from test_pi3_servicio_posicion_inicial import (BRAQUI_00, EPSON009, S1, S2, SERIE_A, SERIE_B, USUARIO, _sembrar, bd, plantilla)  # noqa: F401
from test_pi7_pdf_mensual_posicion_inicial import _con_condiciones, rm  # noqa: F401
from test_pi8_pdf_diario_posicion_inicial import _insertar_braqui
from test_r1_r6_reportes_diarios_legibles import (DICC_BRAQUI, _AutoDB, _sin_dialogos_modales, app, bd_temporal)  # noqa: F401

ESPACIO_DURO = " "
FECHA_DIARIO = "2026-03-01"               # dentro del periodo de la fuente S1 (S1 = 2026-01-10, hasta S2 = 2026-04-15)
TITULO = "Posición inicial de la fuente"
ANCHO_FIGURA_PT, ALTO_FIGURA_PT = 420, 400
_CACHE = {}                               # el analisis de la placa real (EPSON009), una vez por modulo (0.4 s): lo suelta `liberar_el_analisis` al terminar el modulo (test_b4_los_caches...)


# ------------------------------------------------------------------------------------------------------------- lo esperado (independiente del servicio)

# Como se dice una capa en una frase con «capa»: el sustantivo es femenino, asi que «capa roja» (no «capa rojo»). Escrito AQUI y no tomado de una constante del codigo: el oraculo no puede ser lo que se
# prueba (R1-PROD-01: con `NOMBRE_DE_CAPA`, la tabla de los colores de los menus -rojo, verde, azul-, la prueba esperaba lo mismo que el codigo y no veia «Capa rojo» en un documento firmado).
CAPA_EN_UNA_FRASE = {"R": "capa roja", "G": "capa verde", "B": "capa azul"}


def _analisis():
    """El analisis de EPSON009 con los clics del fisico: lo mide el servicio (`analizar_imagen`, el unico camino de una imagen real hacia el motor)."""
    if "epson009" not in _CACHE:
        _CACHE["epson009"] = svc.analizar_imagen(EPSON009, CLICS_EPSON009)
    return _CACHE["epson009"]


def liberar_el_analisis():
    """Suelta el analisis guardado (sus imagenes de la ventana y los perfiles son varios MB): lo llama la fixture de modulo de abajo al terminar el archivo."""
    _CACHE.clear()
    gc.collect()


@pytest.fixture(scope="module", autouse=True)
def _suelta_el_analisis():
    yield
    liberar_el_analisis()


def _n(valor, decimales):
    """El numero con sus decimales y nunca '-0.00' (lo que el PDF imprime): escrito aqui aparte, no tomado de la pagina."""
    texto = f"{valor:.{decimales}f}"
    return texto[1:] if texto.startswith("-") and float(texto) == 0 else texto


def _normal(texto):
    return " ".join(texto.replace(ESPACIO_DURO, " ").split())


def _linea_esperada(capa, fecha=S1):
    """La linea del bloque de la capa `capa`, construida de `motor.resumen` (lo que la pantalla muestra) y no del servicio: «Capa verde: -0.10 ± 0.16 mm (k = 2),
    antes de la marca. Cumple (tolerancia 1.0 mm). Cambio de fuente del 2026-01-10»."""
    s = motor.resumen(_analisis(), capa)
    assert s["estado"] == "ok", (capa, s)
    return (f"{CAPA_EN_UNA_FRASE[capa].capitalize()}: {_n(s['desfase_fisico_mm'], 2)} ± {_n(s['U_mm'], 2)} mm (k = 2), {s['sentido']}. {s['veredicto']} "
            f"(tolerancia 1.0 mm). Cambio de fuente del {fecha}")


def _numeros_de(perfil):
    """Las cadenas numericas que el bloque imprime de un perfil (mediana, media y desviacion en mm con 3 decimales y en px con 2): lo que identifica de que perfil son."""
    r = _analisis()["perfiles"][perfil]
    tam = _analisis()["tamano_pixel_mm"]
    salida = {}
    for clave, px in (("mediana", r["desfase_px"]), ("media", r["media_px"]), ("desviacion", r["dispersion_px"])):
        salida[clave] = (_n(px * tam, 3), _n(px, 2))
    salida["filas"] = str(len(r["filas"]))
    return salida


def _aparece(numero, texto):
    """El numero como palabra aparte, con su signo (que «-0.10» no cuente dentro de «-0.109», «2.30» dentro de «12.301» ni «3.34» dentro de «-3.34»: otra medida con otro signo)."""
    return re.search(rf"(?<![\d.\-]){re.escape(numero)}(?![\d])", texto) is not None


# ------------------------------------------------------------------------------------------------------------------------------- el PDF DIARIO

def _sembrar_diario(bd_temporal, capa, imagen=EPSON009, clics=CLICS_EPSON009):
    """Dos cambios de fuente (S1 serie A, S2 serie B), un diario de braquiterapia del 2026-03-01 (periodo de S1, sin analisis ni pelicula: el bloque es lo unico que
    se mide) y la prueba de S1 guardada con el escritor REAL del servicio y la capa pedida (None = sin capa)."""
    _insertar_braqui(bd_temporal, FECHA_DIARIO, con_analisis=False)
    for fecha, serie in ((f"{S1} 15:03:03", SERIE_A), (f"{S2} 09:30:00", SERIE_B)):
        bd_temporal.con.execute("INSERT INTO TipoCalibracion (user, fecha, tipo, serie, activo) VALUES ('Siembra', ?, 'Cambio de fuente', ?, 1)", (fecha, serie))
    bd_temporal.con.commit()
    return svc.guardar(USUARIO, S1, imagen, "EPSON009.jpeg", clics, capa_reportada=capa)


def _pdf_diario(monkeypatch, fecha=FECHA_DIARIO):
    """Los BYTES del PDF que genera `reportes.reporte()` real (sin QFileDialog ni ventana)."""
    capturado = {}

    class _FalsoVisor:
        def __init__(self, pdf_data=None, **k):
            capturado["bytes"] = pdf_data

        def show(self):
            pass

    monkeypatch.setattr(reportes_mod, "PdfViewer", _FalsoVisor)
    reportes_mod.reporte(_AutoDB(), fecha=fecha, maquina="Gammamed Plus i X", id_maquina="", tipo_reporte="diario", diccionario=DICC_BRAQUI, umbrales="si", file_name="")
    assert "bytes" in capturado, "el diario no generó ningún PDF"
    return bytes(capturado["bytes"])


def _texto(pdf):
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        return "\n".join(pagina.get_text() for pagina in doc)
    finally:
        doc.close()


def _imagenes(pdf):
    """[(pagina, rectangulo, xref, ancho_px, alto_px)] de las imagenes embebidas en el PDF."""
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        return [(i, fitz.Rect(info["bbox"]), info["xref"], info["width"], info["height"])
                for i, pagina in enumerate(doc) for info in pagina.get_image_info(xrefs=True)]
    finally:
        doc.close()


def _figuras(pdf):
    """Las imagenes del PDF que miden 420 x 400 pt: la figura del bloque."""
    return [im for im in _imagenes(pdf) if abs(im[1].width - ANCHO_FIGURA_PT) < 1 and abs(im[1].height - ALTO_FIGURA_PT) < 1]


class TestElDiarioDiceLaCapaQueGuardoElRegistro:
    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_bloque_dice_el_nombre_y_los_numeros_de_esa_capa_y_ninguno_de_otra(self, app, bd_temporal, monkeypatch, capa):
        _sembrar_diario(bd_temporal, capa)
        pdf = _pdf_diario(monkeypatch)
        texto = _normal(_texto(pdf))
        assert texto.count(TITULO) == 1
        assert TITULO in [linea.strip() for linea in _texto(pdf).splitlines()], "la cabecera del bloque debe ser EXACTAMENTE el titulo, sin la capa ni nada pegado (M18)"
        # la linea (desfase ± U, sentido, veredicto), con el nombre de la capa
        assert _linea_esperada(capa) in texto, f"el diario no dice la linea de la capa {capa}"
        propios = _numeros_de(capa)
        for clave in ("mediana", "media", "desviacion"):
            mm, px = propios[clave]
            assert _aparece(mm, texto) and _aparece(px, texto), f"falta la {clave} de la capa {capa} ({mm} mm, {px} px)"
        assert re.search(rf"(?<!\d){propios['filas']}(?!\d)", texto.split(TITULO, 1)[1]), "falta el numero de filas de la capa"
        # ninguna cifra de otro perfil (el gris y las otras dos capas)
        for otro in ("gris",) + tuple(c for c in CAPAS if c != capa):
            ajenos = _numeros_de(otro)
            for clave in ("mediana", "media", "desviacion"):
                for numero in ajenos[clave]:
                    if numero not in propios[clave]:
                        assert not _aparece(numero, texto.split(TITULO, 1)[1]), f"el diario de la capa {capa} imprime la {clave} de {otro} ({numero})"
        # el nombre de la capa de ESTE registro y ninguno de las otras
        assert CAPA_EN_UNA_FRASE[capa] in texto.lower(), f"el diario de la capa {capa} no dice «{CAPA_EN_UNA_FRASE[capa]}»"
        for otra in (c for c in CAPAS if c != capa):
            assert CAPA_EN_UNA_FRASE[otra] not in texto.lower(), f"el diario de la capa {capa} nombra la capa {otra}"
        assert "capa rojo" not in texto.lower(), "«capa rojo» no concuerda: el sustantivo es femenino (R1-PROD-01)"

    def test_la_linea_ocupa_una_fila_de_ancho_completo_y_no_la_columna_de_los_rotulos(self, app, bd_temporal, monkeypatch):
        """La linea (desfase ± U, sentido y veredicto) va en una fila de los 450 pt de la tabla: a 8 pt son uno o dos renglones; en la columna de 225 pt serian tres o mas."""
        _sembrar_diario(bd_temporal, "R")
        doc = fitz.open(stream=_pdf_diario(monkeypatch), filetype="pdf")
        try:
            pagina = next(p for p in doc if p.search_for(TITULO))
            palabras = pagina.get_text("words")
            inicio = next(w for w in palabras if w[4] == "Capa" and w[0] < 100)
            renglones = {round(w[1]) for w in palabras if w[1] >= inicio[1] - 1 and w[3] <= inicio[3] + 22 and w[4] not in ("Capa", "reportada")}
            ancho = max(w[2] for w in palabras if inicio[1] - 1 <= w[1] <= inicio[3] + 22) - inicio[0]
            assert ancho > 300 and len(renglones) <= 2, (ancho, sorted(renglones))
        finally:
            doc.close()

    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_bloque_lleva_la_figura_de_la_capa_en_la_misma_pagina_que_su_tabla(self, app, bd_temporal, monkeypatch, capa):
        _sembrar_diario(bd_temporal, capa)
        pdf = _pdf_diario(monkeypatch)
        figuras = _figuras(pdf)
        assert len(figuras) == 1, f"el bloque debe llevar UNA figura de {ANCHO_FIGURA_PT} x {ALTO_FIGURA_PT} pt (hay {len(figuras)})"
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            pagina_figura = figuras[0][0]
            titulos = [(i, r) for i, p in enumerate(doc) for r in p.search_for(TITULO)]
            assert [i for i, _ in titulos] == [pagina_figura], "la figura y su tabla deben salir en la misma pagina"
            assert titulos[0][1].y1 < figuras[0][1].y0, "la figura va DEBAJO de su tabla"
        finally:
            doc.close()


# ------------------------------------------------------------------------------------------------------------------------------ el PDF MENSUAL

ETIQUETA_DE_LA_FILA = "Desplazamiento inicial (mm)"
TIPOS = (("Cambio de fuente", S1), ("Calibración Redundante", S1), ("Control Mensual", "2026-02-20"))      # (tipo del reporte, la fecha con que se pide: el dia, sin hora)


def _sembrar_mensual(bd, capa, imagen=EPSON009, clics=CLICS_EPSON009):
    """La siembra de PI.3 (dos cambios de fuente, una redundante el mismo dia, un mensual de la serie A), las condiciones de medicion y el maximo minimo de cada calibracion
    de S1 (sin ellos el PDF no se genera) y la prueba de S1 guardada con el escritor REAL y la capa pedida."""
    ids = _sembrar(bd)
    _con_condiciones(bd, ids["s1"], f"{S1} 15:03:03", 0.13)
    _con_condiciones(bd, ids["redundante"], f"{S1} 15:20:00", "No Aplica")
    _con_condiciones(bd, ids["mensual_a"], "2026-02-20 10:00:00", "No Aplica")
    _con_condiciones(bd, ids["s2"], f"{S2} 09:30:00", 0.13)
    return svc.guardar(USUARIO, S1, imagen, "EPSON009.jpeg", clics, capa_reportada=capa), ids


def _pdf_mensual(rm, ruta, fecha, tipo, monkeypatch):
    """Los BYTES del PDF que genera `reporte_mensual()` real (sin abrir el visor); el reporte se traga los errores en un `QMessageBox.critical`: si avisa, la prueba falla."""
    errores, captura = [], {}
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: errores.append(a)))
    for aviso in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, aviso, staticmethod(lambda *a, **k: None))

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

    monkeypatch.setattr(rm, "PdfViewer", FalsoVisor)
    rm.reporte_mensual(Pantalla(), fecha, "Braquiterapia", "IDC", tipo, None, None, "")
    assert not errores, f"el reporte avisó de un error: {errores}"
    assert "pdf" in captura, "no se generó ningún PDF"
    return bytes(captura["pdf"])


class TestElMensualDiceLaCapaQueGuardoElRegistro:
    @pytest.mark.parametrize("capa", CAPAS)
    @pytest.mark.parametrize("tipo,fecha", TIPOS, ids=[t for t, _ in TIPOS])
    def test_la_fila_y_la_seccion_dicen_el_nombre_y_los_numeros_de_esa_capa_y_ninguno_de_otra(self, rm, bd, monkeypatch, capa, tipo, fecha):
        _sembrar_mensual(bd, capa)
        texto = _normal(_texto(_pdf_mensual(rm, bd, fecha, tipo, monkeypatch)))
        esperada = _linea_esperada(capa)
        # la fila «Desplazamiento inicial (mm)» NO se quita: cambia por la linea de la capa reportada
        fila = texto.split(ETIQUETA_DE_LA_FILA, 1)[1]
        assert fila.startswith(" " + esperada), f"la fila {ETIQUETA_DE_LA_FILA!r} no dice la linea de la capa {capa}"
        # y una seccion propia, con las medidas estadisticas de la capa
        assert texto.count(TITULO) == 1, "la seccion «Posición inicial de la fuente» debe salir una vez"
        seccion = texto.split(TITULO, 1)[1]
        propios = _numeros_de(capa)
        for clave in ("mediana", "media", "desviacion"):
            mm, px = propios[clave]
            assert _aparece(mm, seccion) and _aparece(px, seccion), f"falta la {clave} de la capa {capa} ({mm} mm, {px} px)"
        for otro in ("gris",) + tuple(c for c in CAPAS if c != capa):
            ajenos = _numeros_de(otro)
            for clave in ("mediana", "media", "desviacion"):
                for numero in ajenos[clave]:
                    if numero not in propios[clave]:
                        assert not _aparece(numero, texto), f"el mensual de la capa {capa} imprime la {clave} de {otro} ({numero})"
        assert CAPA_EN_UNA_FRASE[capa] in seccion.lower(), f"la seccion del mensual de la capa {capa} no dice «{CAPA_EN_UNA_FRASE[capa]}»"
        for otra in (c for c in CAPAS if c != capa):
            assert CAPA_EN_UNA_FRASE[otra] not in texto.lower(), f"el mensual de la capa {capa} nombra la capa {otra}"
        assert "capa rojo" not in texto.lower(), "«capa rojo» no concuerda: el sustantivo es femenino (R1-PROD-01)"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_seccion_va_tras_las_condiciones_de_medicion_con_su_figura(self, rm, bd, monkeypatch, capa):
        _sembrar_mensual(bd, capa)
        pdf = _pdf_mensual(rm, bd, S1, "Cambio de fuente", monkeypatch)
        texto = _normal(_texto(pdf))
        assert TITULO in texto, "el mensual no tiene la seccion «Posición inicial de la fuente»"
        assert texto.index("Condiciones de medición") < texto.index(TITULO) < texto.index("Máximos de cámaras"), "la seccion va tras «Condiciones de medicion» (B6-F5)"
        assert len(_figuras(pdf)) == 1, f"la seccion debe llevar UNA figura de {ANCHO_FIGURA_PT} x {ALTO_FIGURA_PT} pt"
        assert f"{NOMBRE_DE_PERFIL[capa]} (la reportada)" in texto, "la tabla de la figura se titula con el nombre de la capa y «(la reportada)»"


# ------------------------------------------------------------------------------------------------------------------------------ el servicio

TAM = 25.4 / 600.0


def _registro(capa=None, **extra):
    """Un registro guardado tal como lo entrega el servicio (`posicion_inicial_para`), con el gris y las tres capas MUY distintas: el gris cumple, la roja no, la verde cumple y la azul no se midio. Lo que
    dice cada texto prueba de que capa lo leyo. (Los mm son px x la escala, como los guarda la tabla.)"""
    registro = {"id": 1, "fecha": S1, "serie_fuente": SERIE_A, "tamano_pixel_mm": TAM, "dpi": 600.0, "lado_transito": "derecha", "tolerancia_mm": 1.0, "parametros": "{}",
                "version_algoritmo": motor.VERSION_ALGORITMO, "capa_reportada": capa,
                "estado_gris": "ok", "desfase_gris_px": -2.0, "desfase_gris_mm": -2.0 * TAM, "incertidumbre_gris_px": 1.0, "dispersion_gris_px": 0.5, "media_gris_px": -2.1, "filas_gris": 30,
                "estado_r": "ok", "desfase_r_px": 30.0, "desfase_r_mm": 30.0 * TAM, "incertidumbre_r_px": 3.0, "dispersion_r_px": 2.0, "media_r_px": 29.0, "filas_r": 40,
                "estado_g": "ok", "desfase_g_px": -5.0, "desfase_g_mm": -5.0 * TAM, "incertidumbre_g_px": 2.0, "dispersion_g_px": 1.5, "media_g_px": -5.5, "filas_g": 50,
                "estado_b": "no medible: la mancha esta cortada por el borde de la pelicula", "desfase_b_px": None, "desfase_b_mm": None, "incertidumbre_b_px": None,
                "dispersion_b_px": None, "media_b_px": None, "filas_b": None}
    registro.update(extra)
    return registro


def _registro_con_las_cuatro_medidas(capa=None, **extra):
    """`_registro` con la azul tambien medida: el gris y las tres capas con las siete medidas CADA UNA y todas distintas entre perfiles (px: gris -2, roja 30, verde -5, azul 12), de modo que lo que se
    lee de un perfil solo puede ser de ESE perfil."""
    azul = {"estado_b": "ok", "desfase_b_px": 12.0, "desfase_b_mm": 12.0 * TAM, "incertidumbre_b_px": 4.0, "dispersion_b_px": 3.0, "media_b_px": 11.0, "filas_b": 60}
    return _registro(capa, **{**azul, **extra})


# Lo que `_registro_con_las_cuatro_medidas` guarda de cada perfil, escrito AQUI (el oraculo del bloque: las siete medidas de un perfil y ninguna de otro), y el texto de cada capa sin el cambio de fuente.
LO_GUARDADO = {
    "gris": {"estado": "ok", "medidas": {"desfase_px": -2.0, "desfase_mm": -2.0 * TAM, "media_px": -2.1, "dispersion_px": 0.5, "filas": 30, "incertidumbre_px": 1.0}},
    "R": {"estado": "ok", "medidas": {"desfase_px": 30.0, "desfase_mm": 30.0 * TAM, "media_px": 29.0, "dispersion_px": 2.0, "filas": 40, "incertidumbre_px": 3.0}},
    "G": {"estado": "ok", "medidas": {"desfase_px": -5.0, "desfase_mm": -5.0 * TAM, "media_px": -5.5, "dispersion_px": 1.5, "filas": 50, "incertidumbre_px": 2.0}},
    "B": {"estado": "ok", "medidas": {"desfase_px": 12.0, "desfase_mm": 12.0 * TAM, "media_px": 11.0, "dispersion_px": 3.0, "filas": 60, "incertidumbre_px": 4.0}}}
TEXTO_DE_CADA_PERFIL = {
    None: "-0.08 ± 0.04 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm)",
    "R": "Capa roja: 1.27 ± 0.13 mm (k = 2), despues de la marca. No cumple (tolerancia 1.0 mm)",
    "G": "Capa verde: -0.21 ± 0.08 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm)",
    "B": "Capa azul: 0.51 ± 0.17 mm (k = 2), despues de la marca. Cumple (tolerancia 1.0 mm)"}


class TestElTextoBreveLeeLaCapaDelRegistro:
    def test_sin_capa_es_el_texto_de_siempre_del_gris_sin_nombre_de_capa(self):
        texto = svc.texto_breve(_registro(None))
        assert texto == "-0.08 ± 0.04 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm). Cambio de fuente del 2026-01-10", texto
        assert "Capa" not in texto
        assert svc.texto_breve(_registro("")) == texto, "una capa vacia es no tener capa"

    @pytest.mark.parametrize("capa,esperado", [
        ("R", "Capa roja: 1.27 ± 0.13 mm (k = 2), despues de la marca. No cumple (tolerancia 1.0 mm). Cambio de fuente del 2026-01-10"),
        ("G", "Capa verde: -0.21 ± 0.08 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm). Cambio de fuente del 2026-01-10"),
        ("B", "Capa azul: No medible: la mancha esta cortada por el borde de la pelicula. Cambio de fuente del 2026-01-10")])
    def test_cada_capa_dice_su_nombre_y_sus_numeros_y_ninguno_del_gris(self, capa, esperado):
        """R1-PROD-01: «Capa roja» (el sustantivo «capa» es femenino), escrito aqui literal y no tomado de una constante del codigo."""
        assert svc.texto_breve(_registro(capa)) == esperado

    def test_el_veredicto_y_el_sentido_son_los_de_la_capa_y_no_los_del_gris(self):
        """M2: con el gris que cumple, la capa roja que NO cumple y el lado `izquierda`, cada una dice lo suyo."""
        gris, roja = svc.texto_breve(_registro(None, lado_transito="izquierda")), svc.texto_breve(_registro("R", lado_transito="izquierda"))
        assert "Cumple" in gris and "No cumple" not in gris and "No cumple" in roja
        assert "despues de la marca" in gris and "antes de la marca" in roja, "el sentido fisico sale del desfase de la capa y del lado de transito"

    def test_con_capa_sin_milimetros_ni_escala_dice_los_pixeles_de_esa_capa(self):
        texto = svc.texto_breve(_registro("R", tamano_pixel_mm=None, dpi=300.0))
        assert texto.startswith("Capa roja: 30.00 ± 3.00 px (k = 2); ") and "mm (k" not in texto

    @pytest.mark.parametrize("capa,esperado", [
        ("R", "Capa roja: 1.27 ± 0.13 mm (k = 2), despues de la marca. No cumple (tolerancia 1.0 mm)"),
        ("G", "Capa verde: -0.21 ± 0.08 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm)"),
        ("B", "Capa azul: No medible: la mancha esta cortada por el borde de la pelicula")])
    def test_sin_el_cambio_de_fuente_la_linea_conserva_el_nombre_de_su_capa_y_termina_en_el_veredicto(self, capa, esperado):
        """R1P-01 (revision, ronda 1): la tabla de registros de la pagina pide el texto con `con_cambio_de_fuente=False` (su columna del cambio de fuente ya existe): sin ese final la linea es la misma,
        CON el nombre de su capa. Antes solo se afirmaba el final del texto de la verde, y un texto breve que omitiera el nombre de la capa en ese modo no lo atrapaba ninguna prueba."""
        registro = _registro(capa)
        assert svc.texto_breve(registro, con_cambio_de_fuente=False) == esperado
        assert svc.texto_breve(registro, con_cambio_de_fuente=True) == esperado + f". Cambio de fuente del {S1}", "con el cambio de fuente es la misma linea con su final"

    def test_sin_capa_y_sin_el_cambio_de_fuente_es_el_texto_de_siempre_sin_nombre_de_capa(self):
        texto = svc.texto_breve(_registro(None), con_cambio_de_fuente=False)
        assert texto == "-0.08 ± 0.04 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm)" and "Capa" not in texto

    def test_el_texto_para_pdf_y_el_bloque_dicen_lo_mismo(self):
        registro = _registro("R")
        assert svc.unir_numero_y_unidad(svc.texto_breve(registro)).count(ESPACIO_DURO) >= 2
        assert svc.bloque_pdf_posicion_inicial({**registro, "version_algoritmo": "otra"})["linea"] == svc.unir_numero_y_unidad(svc.texto_breve(registro))


class TestCapaDelRegistro:
    @pytest.mark.parametrize("valor", [None, ""])
    def test_vacia_o_ausente_es_el_gris(self, valor):
        assert svc.capa_del_registro({"capa_reportada": valor}) == svc.PERFIL_SIN_CAPA == "gris"
        assert svc.capa_del_registro({}) == "gris"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_r_g_b_son_ellas_mismas(self, capa):
        assert svc.capa_del_registro({"capa_reportada": capa}) == capa

    @pytest.mark.parametrize("valor", ["g", "r", "gris", "verde", "X", "RG", " G", 1, 0, True])
    def test_otra_cosa_es_un_dato_danado_y_no_se_imprime_otra_capa_en_silencio(self, valor):
        with pytest.raises(svc.PosicionInicialError):
            svc.capa_del_registro({"capa_reportada": valor})

    def test_un_registro_con_la_capa_danada_no_genera_un_texto(self):
        with pytest.raises(svc.PosicionInicialError):
            svc.texto_breve(_registro("g"))
        with pytest.raises(svc.PosicionInicialError):
            svc.bloque_pdf_posicion_inicial(_registro("g"))


class TestElBloqueDelServicio:
    def test_el_bloque_trae_lo_guardado_de_la_capa_y_ninguna_otra(self):
        bloque = svc.bloque_pdf_posicion_inicial(_registro("G", version_algoritmo="OTRA"))
        assert bloque["capa"] == "G" and bloque["capa_guardada"] is True and bloque["estado"] == "ok"
        assert bloque["medidas"] == {"desfase_px": -5.0, "desfase_mm": -5.0 * TAM, "media_px": -5.5, "dispersion_px": 1.5, "filas": 50, "incertidumbre_px": 2.0}
        assert bloque["tamano_pixel_mm"] == TAM and bloque["dpi"] == 600.0 and bloque["fecha"] == S1 and bloque["version_guardada"] == "OTRA"
        assert bloque["parametros"]["resolucion_escaneo_dpi"] == motor.PARAMETROS["resolucion_escaneo_dpi"] and bloque["parametros"]["tolerancia_mm"] == 1.0

    def test_sin_capa_es_el_gris_y_el_bloque_lo_dice(self):
        bloque = svc.bloque_pdf_posicion_inicial(_registro(None, version_algoritmo="OTRA"))
        assert bloque["capa"] == "gris" and bloque["capa_guardada"] is False
        assert bloque["medidas"]["desfase_px"] == -2.0 and bloque["medidas"]["filas"] == 30

    def test_una_capa_que_no_se_midio_trae_las_medidas_vacias_y_el_estado(self):
        bloque = svc.bloque_pdf_posicion_inicial(_registro("B", version_algoritmo="OTRA"))
        assert bloque["estado"].startswith("no medible") and set(bloque["medidas"].values()) == {None}

    def test_el_bloque_para_pdf_usa_la_regla_de_vigencia_y_da_none_sin_prueba(self, bd):
        _sembrar(bd)
        assert svc.bloque_para_pdf(S1) is None and svc.bloque_para_pdf(S1, serie=SERIE_A) is None
        svc.guardar(USUARIO, S1, EPSON009, "EPSON009.jpeg", CLICS_EPSON009, capa_reportada="G")
        assert svc.bloque_para_pdf("2026-03-01")["capa"] == "G"                                      # sin serie (el diario)
        assert svc.bloque_para_pdf("2026-03-01", serie=SERIE_A)["capa"] == "G"                       # con la serie de la fuente (el mensual)
        assert svc.bloque_para_pdf("2026-03-01", serie=SERIE_B) is None                              # DD8: la serie de otra fuente
        assert svc.bloque_para_pdf(S2) is None and svc.bloque_para_pdf("no es una fecha") is None    # el cambio de fuente siguiente: otra fuente, sin prueba

    def test_con_la_tolerancia_de_PI3(self):
        assert svc.TOLERANCIA_AL_RECONSTRUIR_PX == 0.01


class TestCadaPerfilLeeSusSieteColumnasYNingunaDeOtro:
    """R1P-03 (revision, ronda 1): sustituye a la prueba que buscaba `capa.lower()` en el TEXTO del codigo fuente (vigilaba como se escribe el codigo, no la garantia: un refactor que conserva el
    comportamiento, como guardar `sufijo = capa.casefold()`, la rompia con todas las pruebas de comportamiento en verde). La garantia es de comportamiento: el estado, el desfase (px y mm), la
    incertidumbre, la dispersion, la media y el numero de filas que el servicio lee son los del perfil que reporto el registro -el gris si no reporto ninguna capa- y ninguno de otro perfil. Que ningun
    codigo escriba la letra de una capa a mano lo vigila el tripwire por AST de `TestNingunaCapaEscritaAManoNiLeidaDeLaConstante`."""

    @pytest.mark.parametrize("capa", (None,) + CAPAS)
    def test_el_bloque_trae_las_siete_medidas_del_perfil_del_registro_y_ninguna_de_otro(self, capa):
        propio = "gris" if capa is None else capa
        bloque = svc.bloque_pdf_posicion_inicial(_registro_con_las_cuatro_medidas(capa, version_algoritmo="OTRA"))
        assert bloque["estado"] == LO_GUARDADO[propio]["estado"] and bloque["medidas"] == LO_GUARDADO[propio]["medidas"]
        assert all(bloque["medidas"] != LO_GUARDADO[otro]["medidas"] for otro in LO_GUARDADO if otro != propio), "la prueba no distingue un perfil de otro"

    @pytest.mark.parametrize("capa", (None,) + CAPAS)
    def test_el_texto_breve_lee_el_estado_el_desfase_y_la_incertidumbre_del_perfil_del_registro(self, capa):
        assert svc.texto_breve(_registro_con_las_cuatro_medidas(capa), con_cambio_de_fuente=False) == TEXTO_DE_CADA_PERFIL[capa]

    @pytest.mark.parametrize("capa", (None,) + CAPAS)
    def test_el_texto_breve_y_el_bloque_leen_el_estado_del_perfil_del_registro(self, capa):
        """El ESTADO de ese perfil: si no se midio, la linea y el bloque lo dicen aunque los otros tres perfiles esten medidos («ok»). (Con los cuatro «ok» de `_registro_con_las_cuatro_medidas`,
        leer el estado de otro perfil no se veria: la mutacion R1P-03a lo atrapaba solo la prueba de abajo, no la que lleva «lee_el_estado» en su nombre.)"""
        propio = "gris" if capa is None else capa
        registro = _registro_con_las_cuatro_medidas(capa, version_algoritmo="OTRA", **{f"estado_{propio.lower()}": "no medible: no se midio este perfil"})
        esperado = ("" if capa is None else CAPA_EN_UNA_FRASE[capa].capitalize() + ": ") + "No medible: no se midio este perfil"
        assert svc.texto_breve(registro, con_cambio_de_fuente=False) == esperado
        assert svc.bloque_pdf_posicion_inicial(registro)["estado"] == "no medible: no se midio este perfil"

    @pytest.mark.parametrize("capa", (None,) + CAPAS)
    def test_alterar_todo_lo_de_los_otros_perfiles_no_cambia_ni_el_texto_ni_el_bloque(self, capa):
        """Lo de los demas perfiles puede valer cualquier cosa (otro estado, otro desfase, otra media...) sin que cambie nada de lo que se imprime del perfil del registro."""
        propio = "gris" if capa is None else capa
        base = _registro_con_las_cuatro_medidas(capa, version_algoritmo="OTRA")
        ajeno = dict(base)
        for otro in (p for p in LO_GUARDADO if p != propio):
            s = otro.lower()
            ajeno.update({f"estado_{s}": "no medible: otro", f"desfase_{s}_px": 99.0, f"desfase_{s}_mm": 99.0 * TAM, f"incertidumbre_{s}_px": 9.0, f"dispersion_{s}_px": 9.0, f"media_{s}_px": 99.0,
                          f"filas_{s}": 1})
        assert ajeno != base
        assert svc.texto_breve(ajeno) == svc.texto_breve(base)
        assert svc.bloque_pdf_posicion_inicial(ajeno) == svc.bloque_pdf_posicion_inicial(base)

    @pytest.mark.parametrize("perfil", ("gris",) + CAPAS)
    def test_las_claves_de_un_perfil_son_sus_siete_medidas_y_ninguna_de_otro(self, perfil):
        """`_claves_de_la_capa` (de donde sale lo que se compara al volver a medir): las siete medidas de `valores_medidos` de ese perfil. Los nombres de columna estan escritos aqui."""
        s = perfil.lower()
        esperadas = {f"estado_{s}", f"desfase_{s}_px", f"desfase_{s}_mm", f"incertidumbre_{s}_px", f"dispersion_{s}_px", f"media_{s}_px", f"filas_{s}"}
        valores = motor.valores_medidos(_analisis())
        assert esperadas <= set(valores), "compuerta: `valores_medidos` produce las siete medidas de cada perfil"
        assert set(svc._claves_de_la_capa(valores, perfil)) == esperadas


# ------------------------------------------------------------------------------------------ cuando se dibuja el perfil y cuando no (la reconstruccion)

import sqlite3                                                           # noqa: E402

import ui.paginasControles.PruebasMensuales.posicion_inicial_braqui as pagina_mod      # noqa: E402
from test_pi3_servicio_posicion_inicial import _sql                      # noqa: E402


def _guardado(bd, capa="G", imagen=EPSON009, clics=CLICS_EPSON009):
    """La BD de PI.3 con la siembra y la prueba de S1 guardada con el escritor real y la capa pedida: devuelve el id."""
    _sembrar(bd)
    return svc.guardar(USUARIO, S1, imagen, "EPSON009.jpeg", clics, capa_reportada=capa)


def _cuenta_los_analisis(monkeypatch):
    """Un espia de `motor.analizar` (lo que `analizar_imagen` llama): cuenta cuantas veces se vuelve a medir."""
    llamadas = []
    real = motor.analizar

    def espia(*a, **k):
        llamadas.append(1)
        return real(*a, **k)

    monkeypatch.setattr(motor, "analizar", espia)
    return llamadas


def _error_log(monkeypatch, tmp_path):
    ruta = tmp_path / "error_log.txt"
    monkeypatch.setenv("RADQA_ERROR_LOG", str(ruta))
    return ruta


def _mover_el_desfase(bd, id_registro, perfil, sumar):
    """Cambia el desfase guardado de un perfil (px y mm a la vez: el CHECK de la tabla exige mm = px x escala)."""
    _sql(bd, f"UPDATE braqui_posicion_inicial SET desfase_{perfil}_px = desfase_{perfil}_px + ?, desfase_{perfil}_mm = (desfase_{perfil}_px + ?) * tamano_pixel_mm WHERE id = ?",
         (sumar, sumar, id_registro))


class TestSoloSeDibujaSiLaVersionEsLaDeHoyYLoGuardadoSeReproduce:
    def test_con_la_version_de_hoy_se_reconstruye_una_vez_y_el_bloque_trae_el_analisis(self, bd, monkeypatch):
        _guardado(bd)
        llamadas = _cuenta_los_analisis(monkeypatch)
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert len(llamadas) == 1 and bloque["resultado"] is not None and bloque["sin_perfil"] is None
        assert bloque["resultado"]["version"] == motor.VERSION_ALGORITMO == bloque["version_guardada"]

    @pytest.mark.parametrize("version", ["PI-1", "PI-3", "pi-2", "PI-2 ", ""], ids=["anterior", "posterior", "minuscula", "con_espacio", "vacia"])
    def test_con_otra_version_ni_se_reconstruye_y_el_bloque_lo_dice_con_lo_guardado(self, bd, monkeypatch, version):
        """B6-F2 / M6: otra version (cadena exacta; una nula o vacia es distinta) = valores y frase, ninguna imagen y CERO llamadas a `analizar`."""
        id_registro = _guardado(bd)
        _sql(bd, "UPDATE braqui_posicion_inicial SET version_algoritmo = ? WHERE id = ?", (version, id_registro))
        llamadas = _cuenta_los_analisis(monkeypatch)
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert llamadas == [], "con otra version no se debe volver a medir"
        assert bloque["resultado"] is None and bloque["version_guardada"] == version
        assert bloque["sin_perfil"] == svc.FRASE_OTRA_VERSION.format(guardada=version or "sin dato", actual=motor.VERSION_ALGORITMO)
        assert motor.VERSION_ALGORITMO in bloque["sin_perfil"]
        assert bloque["linea"] == svc.unir_numero_y_unidad(svc.texto_breve(svc.posicion_inicial_para(FECHA_DIARIO))), "lo impreso es lo guardado"
        assert bloque["medidas"]["desfase_px"] is not None

    @pytest.mark.parametrize("sumar,se_dibuja", [(0.0, True), (0.005, True), (0.0099, True), (0.02, False), (-0.02, False), (0.5, False)])
    def test_el_desfase_guardado_distinto_en_mas_de_0_01_px_no_se_dibuja(self, bd, sumar, se_dibuja):
        """B6-F2 / M8: la coincidencia. +0.02 px = sin figura; +0.005 = con figura."""
        id_registro = _guardado(bd)
        if sumar:
            _mover_el_desfase(bd, id_registro, "g", sumar)
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert (bloque["resultado"] is not None) is se_dibuja, sumar
        assert bloque["sin_perfil"] == (None if se_dibuja else svc.FRASE_NO_COINCIDE)

    @pytest.mark.parametrize("sumar", [0.005, 0.02])
    def test_en_el_mismo_umbral_la_pagina_opina_igual(self, bd, sumar):
        """`diferencias_con_lo_guardado` (lo que la pagina compara al abrir un registro) y el servicio (lo que decide dibujar el PDF) cortan en el mismo umbral de DD3: 0.01 px."""
        id_registro = _guardado(bd)
        _mover_el_desfase(bd, id_registro, "g", sumar)
        registro = svc.leer(id_registro)
        resultado = svc.analizar_imagen(registro["imagen"], __import__("json").loads(registro["puntos"]), __import__("json").loads(registro["parametros"]))
        pagina_dice_que_difiere = bool(pagina_mod.diferencias_con_lo_guardado(registro, resultado))
        servicio_dibuja = svc.bloque_para_pdf(FECHA_DIARIO)["resultado"] is not None
        assert pagina_dice_que_difiere == (not servicio_dibuja) == (sumar > svc.TOLERANCIA_AL_RECONSTRUIR_PX)

    def test_dentro_de_la_tolerancia_se_dibuja_pero_lo_impreso_es_lo_guardado_y_no_lo_recalculado(self, bd):
        """M7: la media guardada +0.0099 px (dentro de los 0.01 de la tolerancia) coincide, asi que se dibuja; pero la fila imprime la GUARDADA, que a dos decimales ya no es la recalculada."""
        id_registro = _guardado(bd)
        recalculada = svc.bloque_para_pdf(FECHA_DIARIO)["medidas"]["media_px"]
        _sql(bd, "UPDATE braqui_posicion_inicial SET media_g_px = media_g_px + 0.0099 WHERE id = ?", (id_registro,))
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert bloque["resultado"] is not None, "dentro de la tolerancia debe dibujarse"
        assert bloque["medidas"]["media_px"] == pytest.approx(recalculada + 0.0099, abs=1e-12) != recalculada
        fila = dict(bp.filas_del_bloque(bloque))["Media de las filas [mm]"]
        assert fila.endswith(f"= {_n(recalculada + 0.0099, 2)} px") and not fila.endswith(f"= {_n(recalculada, 2)} px"), fila

    def test_se_reconstruye_con_los_parametros_guardados_y_no_con_los_de_hoy(self, bd):
        """M13: un registro medido con otros parametros (aqui, `delta` = 5.0) se reconstruye con ESOS: sus medidas guardadas son las de ese analisis, asi que coincide y se dibuja con los
        parametros del registro. Con los de hoy (`motor.PARAMETROS`) saldrian otras medidas y no se dibujaria."""
        import json
        id_registro = _guardado(bd)
        registro = svc.leer(id_registro)
        parametros = {**json.loads(registro["parametros"]), "delta": 5.0}
        resultado = svc.analizar_imagen(registro["imagen"], json.loads(registro["puntos"]), parametros)
        nuevos = motor.valores_medidos(resultado)
        assert nuevos["desfase_g_px"] != registro["desfase_g_px"], "la prueba no distingue: con delta 5.0 sale el mismo desfase"
        columnas = [c for c in nuevos if c not in ("tamano_pixel_mm",)]
        _sql(bd, f"UPDATE braqui_posicion_inicial SET parametros = ?, {', '.join(c + ' = ?' for c in columnas)} WHERE id = ?",
             (json.dumps(parametros, sort_keys=True), *[nuevos[c] for c in columnas], id_registro))
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert bloque["resultado"] is not None and bloque["resultado"]["parametros"]["delta"] == 5.0 and bloque["sin_perfil"] is None
        assert bloque["parametros"]["delta"] == 5.0

    @pytest.mark.parametrize("columna,sumar", [("media_g_px", 0.5), ("incertidumbre_g_px", 0.05), ("dispersion_g_px", 0.05), ("filas_g", 1)])
    def test_cualquiera_de_las_siete_medidas_guardadas_distinta_impide_dibujar_y_se_imprime_la_guardada(self, bd, columna, sumar):
        """M7 / media guardada alterada: se imprime la GUARDADA (alterada) y no se dibuja; nunca la recalculada."""
        id_registro = _guardado(bd)
        _sql(bd, f"UPDATE braqui_posicion_inicial SET {columna} = {columna} + ? WHERE id = ?", (sumar, id_registro))
        guardada = svc.leer(id_registro)[columna]
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert bloque["resultado"] is None and bloque["sin_perfil"] == svc.FRASE_NO_COINCIDE
        clave = {"media_g_px": "media_px", "incertidumbre_g_px": "incertidumbre_px", "dispersion_g_px": "dispersion_px", "filas_g": "filas"}[columna]
        assert bloque["medidas"][clave] == guardada

    @pytest.mark.parametrize("sumar_mm,difiere", [(0.0, False), (0.0003, False), (-0.0003, False), (0.001, True), (-0.001, True), (0.01, True)])
    def test_la_tolerancia_de_los_mm_es_la_de_los_px_por_la_escala(self, bd, sumar_mm, difiere):
        """M25: 0.01 px son `0.01 x tamano_pixel_mm` mm (0.0004 mm a 600 dpi), no 0.01 mm. La tabla (su CHECK) no deja que un registro real difiera SOLO en mm, asi que se prueba la funcion pura con el
        registro leido y el mm movido a mano: la unidad de la tolerancia es parte del contrato de la comparacion."""
        import json
        registro = dict(svc.leer(_guardado(bd)))
        resultado = svc.analizar_imagen(registro["imagen"], json.loads(registro["puntos"]), json.loads(registro["parametros"]))
        assert svc._diferencias_de_la_capa(registro, resultado, "G") == [], "el registro tal cual se guardo debe coincidir con lo que sale al volver a medir"
        registro["desfase_g_mm"] += sumar_mm
        diferencias = svc._diferencias_de_la_capa(registro, resultado, "G")
        assert bool(diferencias) is difiere, diferencias
        assert all(d.startswith("desfase_g_mm") for d in diferencias)

    def test_el_estado_guardado_distinto_impide_dibujar(self, bd):
        id_registro = _guardado(bd)
        _sql(bd, "UPDATE braqui_posicion_inicial SET estado_g = 'no medible: otro' WHERE id = ?", (id_registro,))
        assert svc.bloque_para_pdf(FECHA_DIARIO)["sin_perfil"] == svc.FRASE_NO_COINCIDE

    @pytest.mark.parametrize("capa,perfil", [("G", "gris"), ("G", "r"), ("G", "b"), ("R", "gris"), ("R", "g"), ("R", "b"), ("B", "gris"), ("B", "r"), ("B", "g")])
    def test_solo_cuenta_la_capa_reportada_las_otras_alteradas_no_impiden_dibujar(self, bd, capa, perfil):
        """La coincidencia es de ESA capa: el gris y las otras dos capas pueden diferir sin que el bloque de la capa reportada deje de dibujarse. R1P-03: las TRES capas (antes solo la verde: una
        coincidencia que mirara siempre las columnas de la verde pasaba por la verde y no se veia en las otras dos)."""
        id_registro = _guardado(bd, capa)
        _mover_el_desfase(bd, id_registro, perfil, 0.5)
        assert svc.bloque_para_pdf(FECHA_DIARIO)["resultado"] is not None

    @pytest.mark.parametrize("capa", CAPAS)
    def test_alterar_el_desfase_de_la_propia_capa_reportada_impide_dibujar(self, bd, capa):
        """El reverso de la anterior, en las tres capas: lo guardado de LA capa reportada que no se reproduce impide dibujar y se imprime la frase."""
        id_registro = _guardado(bd, capa)
        _mover_el_desfase(bd, id_registro, capa.lower(), 0.5)
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert bloque["resultado"] is None and bloque["sin_perfil"] == svc.FRASE_NO_COINCIDE

    def test_una_columna_guardada_vacia_no_cuenta_como_un_registro_anterior_a_B5(self, bd):
        """Las nulas de un registro anterior a B.5 (las medidas nuevas no se guardaban) no cuentan: no impiden dibujar."""
        id_registro = _guardado(bd)
        _sql(bd, "UPDATE braqui_posicion_inicial SET media_g_px = NULL, dispersion_g_px = NULL, incertidumbre_g_px = NULL, filas_g = NULL WHERE id = ?", (id_registro,))
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert bloque["resultado"] is not None
        assert bloque["medidas"]["media_px"] is None and bloque["medidas"]["filas"] is None, "lo impreso sigue siendo lo guardado (vacio): no se rellena con lo recalculado"

    def test_con_la_capa_reportada_no_medible_se_dibuja_y_las_medidas_dicen_sin_dato(self, bd):
        """Capa reportada no medible (la roja de braqui_00, cortada por el borde): se dibuja (la figura muestra por que) y las medidas quedan vacias."""
        _guardado(bd, "R", BRAQUI_00, CLICS_PLACA_REAL)
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert bloque["resultado"] is not None and bloque["estado"].startswith("no medible") and set(bloque["medidas"].values()) == {None}
        assert bloque["linea"].startswith("Capa roja: No medible: ")


class TestElDetalleDeLoQueNoCoincideQuedaEnElRegistroDeErrores:
    """R1P-02 (revision, ronda 1): la frase del documento no lleva texto tecnico; lo UNICO que dice POR QUE no se dibuja el perfil cuando al volver a medir no salen las medidas guardadas es el detalle
    de `error_log.txt` (que medida difiere, lo guardado y lo recalculado). Las ramas de «no se pudo medir» y «no se pudo dibujar» ya se leian en ese registro; esta rama, solo por la frase."""

    @pytest.mark.parametrize("columna,sumar", [("media_g_px", 0.5), ("incertidumbre_g_px", 0.05), ("dispersion_g_px", 0.05), ("filas_g", 1)])
    def test_la_medida_que_difiere_se_nombra_con_lo_guardado_y_lo_recalculado(self, bd, monkeypatch, tmp_path, columna, sumar):
        id_registro = _guardado(bd)
        _sql(bd, f"UPDATE braqui_posicion_inicial SET {columna} = {columna} + ? WHERE id = ?", (sumar, id_registro))
        guardada = svc.leer(id_registro)[columna]
        registro = _error_log(monkeypatch, tmp_path)
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert bloque["resultado"] is None and bloque["sin_perfil"] == svc.FRASE_NO_COINCIDE
        texto = registro.read_text(encoding="utf-8") if registro.exists() else ""
        assert "B.6" in texto and f"id={id_registro}" in texto and "no salen las medidas guardadas de la capa G" in texto, f"el registro de errores no dice que la posicion inicial no coincide: {texto!r}"
        assert f"{columna}: guardado {guardada!r}, recalculado " in texto, f"el registro de errores no nombra la medida {columna} con lo guardado y lo recalculado: {texto!r}"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_desfase_que_difiere_se_nombra_en_px_y_en_mm_y_la_capa_es_la_reportada(self, bd, monkeypatch, tmp_path, capa):
        id_registro = _guardado(bd, capa)
        _mover_el_desfase(bd, id_registro, capa.lower(), 0.5)
        registro = _error_log(monkeypatch, tmp_path)
        assert svc.bloque_para_pdf(FECHA_DIARIO)["sin_perfil"] == svc.FRASE_NO_COINCIDE
        texto = registro.read_text(encoding="utf-8") if registro.exists() else ""
        s = capa.lower()
        assert f"no salen las medidas guardadas de la capa {capa}" in texto, texto
        assert f"desfase_{s}_px: guardado " in texto and f"desfase_{s}_mm: guardado " in texto and "; desfase_" in texto, f"las dos diferencias (px y mm) van en el detalle, separadas: {texto!r}"

    @pytest.mark.parametrize("version", [None, "PI-1"], ids=["se_reproduce", "otra_version"])
    def test_si_se_reproduce_o_es_otra_version_no_es_un_error_y_no_escribe_nada(self, bd, monkeypatch, tmp_path, version):
        """Control: el registro de errores es para lo que falla. Un bloque que se dibuja, o que no se dibuja porque la version del algoritmo es otra (lo dice el documento), no deja nada ahi."""
        id_registro = _guardado(bd)
        if version:
            _sql(bd, "UPDATE braqui_posicion_inicial SET version_algoritmo = ? WHERE id = ?", (version, id_registro))
        registro = _error_log(monkeypatch, tmp_path)
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert (bloque["resultado"] is None) == bool(version)
        assert not registro.exists(), registro.read_text(encoding="utf-8")


class TestUnFalloAlReconstruirNoTumbaElBloque:
    @pytest.mark.parametrize("columna,valor", [("imagen", b"esto no es una imagen"), ("puntos", "no es json"), ("puntos", "[[1, 2]]"), ("parametros", "no es json"), ("parametros", "[]"),
                                               ("puntos", "[[1, 2], [1, 2]]")],
                             ids=["imagen_ilegible", "puntos_basura", "un_solo_punto", "parametros_basura", "parametros_lista", "puntos_iguales"])
    def test_lo_que_no_se_lee_sale_con_lo_guardado_la_frase_y_el_detalle_en_el_registro_de_errores(self, bd, monkeypatch, tmp_path, columna, valor):
        id_registro = _guardado(bd)
        _sql(bd, f"UPDATE braqui_posicion_inicial SET {columna} = ? WHERE id = ?", (valor, id_registro))
        registro = _error_log(monkeypatch, tmp_path)
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert bloque["resultado"] is None and bloque["sin_perfil"] == svc.FRASE_NO_SE_PUDO_MEDIR
        assert bloque["linea"].startswith("Capa verde: -0.10"), "lo impreso sigue siendo lo guardado"
        assert registro.exists() and "B.6" in registro.read_text(encoding="utf-8") and f"id={id_registro}" in registro.read_text(encoding="utf-8")

    def test_la_frase_no_lleva_texto_tecnico(self):
        for frase in (svc.FRASE_NO_SE_PUDO_MEDIR, svc.FRASE_NO_SE_PUDO_DIBUJAR, svc.FRASE_NO_COINCIDE, svc.FRASE_OTRA_VERSION):
            assert not any(palabra in frase.lower() for palabra in ("traceback", "exception", "error:", "valueerror", "typeerror", "none")), frase

    def test_un_registro_que_ya_no_esta_al_leerlo_sale_con_lo_guardado(self, bd, monkeypatch, tmp_path):
        _guardado(bd)
        registro = _error_log(monkeypatch, tmp_path)
        monkeypatch.setattr(svc, "leer", lambda identificador: None)
        bloque = svc.bloque_para_pdf(FECHA_DIARIO)
        assert bloque["resultado"] is None and bloque["sin_perfil"] == svc.FRASE_NO_SE_PUDO_MEDIR and registro.exists()

    def test_un_fallo_de_la_base_al_leer_la_fila_sube_y_no_sale_un_bloque_dudoso(self, bd, monkeypatch):
        """Regla de PI.8: la base que falla no se disfraza de 'no se pudo dibujar': el PDF no sale."""
        _guardado(bd)

        def revienta(identificador):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(svc, "leer", revienta)
        with pytest.raises(sqlite3.OperationalError):
            svc.bloque_para_pdf(FECHA_DIARIO)

    def test_si_la_fila_ya_trae_la_imagen_no_se_vuelve_a_leer(self, bd, monkeypatch):
        id_registro = _guardado(bd)
        completa = svc.leer(id_registro)
        monkeypatch.setattr(svc, "leer", lambda identificador: pytest.fail("no debia volver a leer la fila"))
        assert svc.bloque_pdf_posicion_inicial(completa)["resultado"] is not None


# ----------------------------------------------------------------------------------------------------------------------------------- la figura

import numpy as np                                                       # noqa: E402

import importlib                                                         # noqa: E402

# la pagina re-exporta los dibujos mudados con el MISMO nombre (existen tambien en HEAD): de ella se leen aqui, para que el archivo se importe contra HEAD
NOMBRE_DE_PERFIL, TRAZO_DE_PARAMETRO = pagina_mod.NOMBRE_DE_PERFIL, pagina_mod.TRAZO_DE_PARAMETRO
datos_del_barrido, fila_representativa = pagina_mod.datos_del_barrido, pagina_mod.fila_representativa


class _ModuloPerezoso:
    """`bp` = `models.PDF.bloque_posicion_inicial`, importado la PRIMERA vez que una prueba lo usa: asi el archivo se importa tambien contra HEAD (que no lo tiene) y las pruebas de punta a punta caen por una
    aserción sobre lo que el PDF dice y no todas por un error de importacion."""

    def __init__(self, nombre):
        self._nombre = nombre

    def __getattr__(self, atributo):
        return getattr(importlib.import_module(self._nombre), atributo)


bp = _ModuloPerezoso("models.PDF.bloque_posicion_inicial")


def _modulo_bp():
    """El modulo REAL (no el proxy): `monkeypatch.setattr` sobre el proxy no parchearia nada."""
    return importlib.import_module("models.PDF.bloque_posicion_inicial")

PERFILES = ("gris",) + CAPAS


def _figura_compuesta(perfil, resultado=None):
    """Una `Figure` con la composicion del PDF ya dibujada (sin guardar nada): para leer lo que dibuja."""
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    with matplotlib.rc_context(bp.LETRA_DE_LA_FIGURA):
        figura = Figure(figsize=(bp.ANCHO_FIGURA_PT / 72.0, bp.ALTO_FIGURA_PT / 72.0), layout="constrained")
        FigureCanvasAgg(figura)
        bp.componer_figura(figura, _analisis() if resultado is None else resultado, perfil)
        figura.canvas.draw()
    return figura


def _lineas_con_etiqueta(eje, empieza):
    return [a for a in eje.get_children() if getattr(a, "get_label", None) and str(a.get_label()).startswith(empieza)]


class TestLaFiguraDelPdf:
    @pytest.mark.parametrize("perfil", PERFILES)
    def test_el_png_mide_420_x_400_pt_a_200_dpi_y_es_un_png(self, perfil):
        png = bp.png_del_perfil(_analisis(), perfil)
        imagen = Image.open(io.BytesIO(png))
        assert imagen.format == "PNG" and imagen.size == (int(ANCHO_FIGURA_PT / 72 * 200), int(ALTO_FIGURA_PT / 72 * 200)) == (1166, 1111), imagen.size      # matplotlib trunca: 420 pt = 1166.67 px
        assert (bp.ANCHO_FIGURA_PT, bp.ALTO_FIGURA_PT, bp.DPI_FIGURA) == (420, 400, 200)

    @pytest.mark.parametrize("capa", CAPAS)
    def test_tres_ejes_la_ventana_el_perfil_y_el_barrido_de_filas_con_su_pie_y_su_titulo(self, capa):
        figura = _figura_compuesta(capa)
        assert len(figura.axes) >= 3
        ventana, perfil, barrido = figura.axes[:3]
        assert ventana.images, "la ventana se dibuja como imagen"
        assert _lineas_con_etiqueta(perfil, "perfil con filtro de mediana") and _lineas_con_etiqueta(perfil, "tope"), "el perfil con su tope"
        assert barrido.get_xlabel().startswith("posición de la fila respecto de la cuerda más ancha"), "el barrido de filas"
        assert figura._suptitle.get_text().startswith(f"{NOMBRE_DE_PERFIL[capa]} (la reportada)"), figura._suptitle.get_text()
        assert figura._supxlabel is not None and "Parámetros fijos del método" in figura._supxlabel.get_text(), "el pie de parámetros fijos (M15)"
        alturas = [eje.get_window_extent().height for eje in (ventana, perfil, barrido)]
        assert bp.ALTOS_DE_LOS_EJES == (1.35, 1.0, 0.9) and alturas[0] > alturas[1] > alturas[2], f"la ventana (la imagen es lo que se mira) es la mas alta: {alturas} (M55)"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_figura_es_la_de_esa_capa_los_datos_de_los_artistas_son_los_de_su_perfil(self, capa):
        """M3: el perfil dibujado es `m['suave'][fila]` de la capa, la ventana es su imagen y el barrido sus filas; no los de otra capa."""
        resultado = _analisis()
        m = resultado["perfiles"][capa]["m"]
        fila = fila_representativa(resultado, "gris")                    # M9: la cuerda dibujada es la del GRIS, la misma con que la pestaña de capas dibuja R, G y B
        figura = _figura_compuesta(capa)
        ventana, perfil, barrido = figura.axes[:3]
        np.testing.assert_array_equal(np.asarray(ventana.images[0].get_array()), m["suave"])
        suave = _lineas_con_etiqueta(perfil, "perfil con filtro de mediana")[0]
        np.testing.assert_array_equal(np.asarray(suave.get_ydata()), m["suave"][fila])
        for otra in (c for c in CAPAS if c != capa):
            assert not np.array_equal(np.asarray(suave.get_ydata()), resultado["perfiles"][otra]["m"]["suave"][fila]), "la prueba no distingue una capa de otra"
        esperados = datos_del_barrido(resultado, capa)
        usadas = [l for l in barrido.get_lines() if str(l.get_label()) == "filas usadas"][0]
        np.testing.assert_allclose(np.asarray(usadas.get_ydata()), esperados["desfase"][esperados["usada"]])
        assert color_de(usadas) == color_de_la_capa(capa)

    def test_la_cuerda_dibujada_es_la_del_gris_y_no_la_de_la_capa(self):
        """M9: en la roja de EPSON009 la cuerda central del gris (38 cuerdas) no es la de la capa (49): si se dibujara la de la capa, el perfil seria otro."""
        resultado = _analisis()
        assert fila_representativa(resultado, "gris") != fila_representativa(resultado, "R"), "la prueba no distingue: las dos cuerdas coinciden"
        figura = _figura_compuesta("R")
        perfil = figura.axes[1]
        crudo = _lineas_con_etiqueta(perfil, "perfil crudo")[0]
        np.testing.assert_array_equal(np.asarray(crudo.get_ydata()), resultado["imagenes"]["R"][fila_representativa(resultado, "gris")])

    def test_las_leyendas_van_fuera_de_su_eje_y_dentro_de_la_figura(self):
        figura = _figura_compuesta("G")
        borde = figura.bbox
        for eje in figura.axes[:3]:
            leyenda = eje.get_legend()
            assert leyenda is not None, "cada eje lleva su leyenda"
            caja, caja_eje = leyenda.get_window_extent(), eje.get_window_extent()
            assert caja.x0 >= caja_eje.x1 - 1, "la leyenda va a la derecha de su eje, no encima de la curva"
            assert caja.x1 <= borde.x1 + 1 and caja.y0 >= borde.y0 - 1 and caja.y1 <= borde.y1 + 1, "la leyenda se recorta"

    def test_la_letra_es_la_del_pdf_de_5_5_a_7_pt(self):
        figura = _figura_compuesta("G")
        tamanos = {round(t.get_fontsize(), 1) for eje in figura.axes[:3] for t in eje.get_xticklabels() + eje.get_yticklabels() if t.get_text()}
        assert tamanos == {5.5}, tamanos
        assert all(5.5 <= l.get_fontsize() <= 8 for eje in figura.axes[:3] for l in eje.get_legend().get_texts()), "la leyenda lleva letra de 5.5 a 8 pt"

    def test_el_pie_se_reparte_al_ancho_de_la_figura_sin_partir_una_frase_en_dos_renglones_largos(self):
        pie = _figura_compuesta("G")._supxlabel.get_text()
        assert max(len(r) for r in pie.split("\n")) <= bp.CARACTERES_POR_RENGLON_DEL_PIE <= 140, "a mas de 140 caracteres por renglon el pie se corta por los dos lados"
        assert " · " in pie and "margen de 3 mm sobre y bajo los puntos" in pie.replace("\n", " ")
        # M49: las frases siguen separadas por « · » tambien donde el pie cambia de renglon (sin el separador, «...de las cuerdas margen de 3 mm...» se leia como una sola frase)
        assert "cuerdas margen de" not in pie.replace("\n", " ") and "cuerdas · margen de" in pie.replace("\n", " ")

    def test_una_capa_que_no_se_midio_se_dibuja_igual_y_su_perfil_dice_no_medible(self):
        resultado = svc.analizar_imagen(BRAQUI_00, CLICS_PLACA_REAL)
        assert resultado["perfiles"]["R"]["estado"].startswith("no medible")
        figura = _figura_compuesta("R", resultado)
        assert "no medible" in figura.axes[1].get_title()
        assert Image.open(io.BytesIO(bp.png_del_perfil(resultado, "R"))).size == (1166, 1111)

    def test_cada_capa_da_una_figura_distinta(self):
        figuras = {perfil: bp.png_del_perfil(_analisis(), perfil) for perfil in PERFILES}
        assert len(set(figuras.values())) == 4, "dos perfiles dieron la misma figura"

    def test_sin_las_capas_la_figura_del_gris_no_dice_la_reportada(self):
        assert not _figura_compuesta("gris")._suptitle.get_text().startswith("Capa")
        assert "(la reportada)" not in _figura_compuesta("gris")._suptitle.get_text()


def color_de(linea):
    import matplotlib.colors as colores
    return colores.to_hex(linea.get_color())


def color_de_la_capa(capa):
    from analisisImagenes.dibujo_posicion_inicial import COLOR_CAPA
    return COLOR_CAPA[capa].lower()


class TestPD1LaFiguraDelPdfDibujaTodoLoQueSeUsoParaMedir:
    """Cada entrada de `TRAZO_DE_PARAMETRO` (el censo de B.1: que trazo o que rotulo muestra cada parametro de la medida) esta en la figura del PDF, en la linea o en la tabla."""

    @pytest.mark.parametrize("clave", sorted(TRAZO_DE_PARAMETRO))
    def test_cada_parametro_tiene_su_trazo_o_su_rotulo_en_el_pdf(self, clave):
        donde, texto = TRAZO_DE_PARAMETRO[clave]
        resultado = _analisis()
        figura = _figura_compuesta("G")
        ventana, perfil, _ = figura.axes[:3]
        P = resultado["parametros"]
        if donde == "perfil":
            assert _lineas_con_etiqueta(perfil, texto), f"{clave}: ningun trazo del perfil empieza por {texto!r}"
        elif donde == "ventana":
            assert any(str(a.get_label()).startswith(texto) for a in ventana.get_children() if hasattr(a, "get_label")), f"{clave}: ningun trazo de la ventana empieza por {texto!r}"
        elif donde == "eje":
            ejes = [c for c in perfil.child_axes if c.get_xlabel().startswith(texto)]
            assert ejes, f"{clave}: el eje secundario en mm no esta"
            limites = ejes[0].get_xlim()
            assert abs(limites[0]) <= P["ventana_mm"] + 0.1 and abs(limites[1]) <= P["ventana_mm"] + 0.1 and max(abs(limites[0]), abs(limites[1])) >= P["ventana_mm"] - 1.0, limites
        elif donde == "recuadro":
            bloque = svc.bloque_pdf_posicion_inicial(_registro("G", version_algoritmo="OTRA"))
            assert f"{texto.lower()} {svc._tolerancia(P[clave])} mm".replace(" mm", ESPACIO_DURO + "mm") in bloque["linea"] or f"{texto.lower()} {svc._tolerancia(P[clave])}" in _normal(bloque["linea"])
        elif donde == "pagina":
            bloque = svc.bloque_pdf_posicion_inicial(_registro("G", version_algoritmo="OTRA"))
            filas = dict(bp.filas_del_bloque(bloque))
            assert filas["Resolución del escaneo [dpi]"] == f"{P[clave]:g}"
        else:
            assert donde == "pie"
            valor = P[clave]
            if isinstance(valor, (list, tuple)):
                valor = ", ".join(f"{v:g}" for v in valor)
            pie = " ".join(figura._supxlabel.get_text().split())
            assert " ".join(texto.format(valor).split()) in pie, f"{clave}: el pie no dice {texto.format(valor)!r}"

    def test_el_censo_no_esta_vacio_y_recorre_las_seis_clases(self):
        assert len(TRAZO_DE_PARAMETRO) >= 20 and {d for d, _ in TRAZO_DE_PARAMETRO.values()} == {"perfil", "ventana", "eje", "recuadro", "pagina", "pie"}


# ---------------------------------------------------------------------------------------------------------------------- las filas de la tabla

class TestLasFilasDelBloque:
    def test_con_capa_y_escala_son_la_capa_reportada_las_tres_medidas_estadisticas_el_numero_de_filas_y_la_resolucion(self):
        bloque = svc.bloque_pdf_posicion_inicial(_registro("G", version_algoritmo="OTRA"))
        assert bp.filas_del_bloque(bloque) == [
            ("Capa reportada", "capa verde"),
            ("Mediana de las filas (el desfase en la imagen) [mm]", "-0.212 = -5.00 px"),
            ("Media de las filas [mm]", "-0.233 = -5.50 px"),
            ("Desviación estándar de las filas [mm]", "0.064 = 1.50 px"),
            ("Número de filas", "50"),
            ("Resolución del escaneo [dpi]", "600"),
            ("Perfil", svc.FRASE_OTRA_VERSION.format(guardada="OTRA", actual=motor.VERSION_ALGORITMO))]

    def test_el_mm_de_la_mediana_es_el_guardado_y_el_de_la_media_y_la_desviacion_es_px_por_la_escala(self):
        """«mm de media y desviacion = px x `tamano_pixel_mm` guardado»; el del desfase es el que se guardo (no se recalcula)."""
        bloque = svc.bloque_pdf_posicion_inicial(_registro("G", version_algoritmo="OTRA", desfase_g_mm=1.0))
        filas = dict(bp.filas_del_bloque(bloque))
        assert filas["Mediana de las filas (el desfase en la imagen) [mm]"] == "1.000 = -5.00 px"
        assert filas["Media de las filas [mm]"] == "-0.233 = -5.50 px"

    def test_sin_escala_solo_pixeles_y_el_rotulo_lo_dice(self):
        bloque = svc.bloque_pdf_posicion_inicial(_registro("R", version_algoritmo="OTRA", tamano_pixel_mm=None, dpi=300.0, desfase_r_mm=None))
        filas = dict(bp.filas_del_bloque(bloque))
        assert filas["Mediana de las filas (el desfase en la imagen) [px]"] == "30.00" and filas["Media de las filas [px]"] == "29.00" and filas["Desviación estándar de las filas [px]"] == "2.00"
        assert not [r for r in filas if r.endswith("[mm]")]

    def test_una_capa_sin_medidas_dice_sin_dato_en_cada_una_y_conserva_el_numero_de_filas_vacio(self):
        bloque = svc.bloque_pdf_posicion_inicial(_registro("B", version_algoritmo="OTRA"))
        filas = bp.filas_del_bloque(bloque)
        assert [valor for rotulo, valor in filas[1:5]] == ["sin dato"] * 4 and filas[0] == ("Capa reportada", "capa azul")

    @pytest.mark.parametrize("declarada", [96.012, 300.0, None], ids=["paint_96", "otra_300", "sin_dato"])
    def test_la_resolucion_es_la_del_procedimiento_con_que_se_midio_y_no_la_que_declara_la_imagen(self, declarada):
        """M40: `EPSON009.jpeg` es un TIFF que Paint dejo en 96.012 dpi, pero el escaneo es de 600 (el procedimiento): la fila dice la resolucion con que se MIDIO. Con la que declara la imagen, un
        documento firmado diria 96 dpi sobre una medida hecha a 600."""
        bloque = svc.bloque_pdf_posicion_inicial(_registro("G", version_algoritmo="OTRA", dpi=declarada))
        assert dict(bp.filas_del_bloque(bloque))["Resolución del escaneo [dpi]"] == f"{motor.PARAMETROS['resolucion_escaneo_dpi']:g}" == "600"

    def test_la_resolucion_es_la_de_los_parametros_guardados_con_la_medida(self):
        """M40: la resolucion del procedimiento es un parametro que se guarda con cada registro (cambiarla en el codigo no reescribe lo guardado): la fila dice la guardada, no la de hoy."""
        import json
        bloque = svc.bloque_pdf_posicion_inicial(_registro("G", version_algoritmo="OTRA", parametros=json.dumps({"resolucion_escaneo_dpi": 300.0})))
        assert bloque["parametros"]["resolucion_escaneo_dpi"] == 300.0
        assert dict(bp.filas_del_bloque(bloque))["Resolución del escaneo [dpi]"] == "300"

    def test_sin_capa_el_bloque_lo_dice(self):
        filas = dict(bp.filas_del_bloque(svc.bloque_pdf_posicion_inicial(_registro(None, version_algoritmo="OTRA"))))
        assert filas["Capa reportada"] == "perfil de grises (el registro no guardó la capa reportada)"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_fila_de_la_capa_reportada_concuerda_con_la_palabra_capa(self, capa):
        """R1-PROD-01: «capa roja» (la fila de la roja decia «capa rojo»: se armaba con la tabla de los colores de los menus, sin concordancia). Las tres, con el nombre escrito aqui."""
        bloque = svc.bloque_pdf_posicion_inicial(_registro_con_las_cuatro_medidas(capa, version_algoritmo="OTRA"))
        assert dict(bp.filas_del_bloque(bloque))["Capa reportada"] == CAPA_EN_UNA_FRASE[capa]

    def test_la_fila_perfil_solo_sale_si_el_perfil_no_se_dibuja(self):
        con_perfil = svc.bloque_pdf_posicion_inicial(_registro("G", version_algoritmo="OTRA"))
        con_perfil["sin_perfil"] = None
        assert "Perfil" not in dict(bp.filas_del_bloque(con_perfil))

    def test_los_rotulos_llevan_la_unidad_en_corchetes_y_ningun_texto_lleva_simbolos_de_correcto_o_incorrecto(self):
        for capa in (None, "R", "G", "B"):
            for fila in bp.filas_del_bloque(svc.bloque_pdf_posicion_inicial(_registro(capa, version_algoritmo="OTRA"))):
                for texto in fila:
                    assert not re.search(r"\((mm|px|dpi)\)", texto), texto
                    assert not any(c in texto for c in "\u2713\u2714\u2717\u2718\u274c\u2705\u26a0"), texto          # DA-18, como escapes: el archivo no lleva el glifo suelto

    def test_las_filas_son_la_unica_definicion_los_dos_pdf_las_piden_a_filas_del_bloque(self, bd):
        _guardado(bd)
        diario, mensual = bp.bloque_del_diario(FECHA_DIARIO), bp.tablas_del_mensual(FECHA_DIARIO, SERIE_A)
        esperadas = bp.filas_del_bloque(svc.bloque_para_pdf(FECHA_DIARIO))
        assert diario["filas"] == esperadas
        assert [tuple(f) for f in mensual[bp.CLAVE_SECCION].values.tolist()[2:]] == esperadas


# --------------------------------------------------------------------------------------------------------------- el modulo del PDF (los dos PDF)

class TestElContenidoDeLosDosPdf:
    def test_sin_prueba_aplicable_no_hay_bloque_ni_secciones(self, bd):
        _sembrar(bd)
        assert bp.bloque_del_diario(FECHA_DIARIO) is None and bp.tablas_del_mensual(FECHA_DIARIO, SERIE_A) == {}

    def test_el_bloque_del_diario_trae_titulo_linea_filas_figura_y_su_tamano(self, bd):
        _guardado(bd, "G")
        bloque = bp.bloque_del_diario(FECHA_DIARIO)
        assert set(bloque) == {"titulo", "linea", "filas", "png", "ancho_pt", "alto_pt"}
        assert bloque["titulo"] == TITULO == bp.TITULO and (bloque["ancho_pt"], bloque["alto_pt"]) == (420, 400)
        assert bloque["linea"] == svc.bloque_para_pdf(FECHA_DIARIO)["linea"] and bloque["linea"].startswith("Capa verde: -0.10")
        assert Image.open(io.BytesIO(bloque["png"])).size == (1166, 1111)

    def test_el_diario_se_pide_sin_serie_y_el_mensual_con_la_serie_de_la_calibracion(self, bd, monkeypatch):
        _guardado(bd)
        llamadas = []
        real = svc.bloque_para_pdf
        monkeypatch.setattr(svc, "bloque_para_pdf", lambda *a, **k: (llamadas.append((a, k)), real(*a, **k))[1])
        bp.bloque_del_diario("2026-03-01")
        bp.tablas_del_mensual("2026-03-01", SERIE_A)
        assert llamadas[0] == (("2026-03-01",), {}) and llamadas[1] == (("2026-03-01", SERIE_A), {})
        assert bp.tablas_del_mensual("2026-03-01", SERIE_B) == {}, "DD8: la serie de otra fuente no lleva la seccion"

    def test_las_tablas_del_mensual_son_dos_con_la_cabecera_de_sus_hermanas_y_la_figura_de_420_x_400_pt(self, bd):
        from reportlab.platypus import Image as FiguraDeReportlab
        _guardado(bd, "B")
        tablas = bp.tablas_del_mensual(FECHA_DIARIO, SERIE_A)
        assert set(tablas) == {bp.CLAVE_SECCION, bp.CLAVE_GRAFICO} == {"posicion_inicial", "grafico_posicion_inicial"}
        seccion = tablas[bp.CLAVE_SECCION]
        assert list(seccion.columns) == [TITULO, ""] and seccion.values.tolist()[0] == ["Campo", "Valor"]
        assert seccion.values.tolist()[1] == ["Resultado", svc.bloque_para_pdf(FECHA_DIARIO, SERIE_A)["linea"]]
        grafico = tablas[bp.CLAVE_GRAFICO]
        assert list(grafico.columns) == ["Capa azul (la reportada)"] and grafico.shape == (1, 1)
        figura = grafico.values.tolist()[0][0]
        assert isinstance(figura, FiguraDeReportlab) and (figura.drawWidth, figura.drawHeight) == (420, 400)

    def test_con_otra_version_el_mensual_lleva_la_seccion_sin_el_grafico_y_el_diario_sin_figura(self, bd):
        id_registro = _guardado(bd)
        _sql(bd, "UPDATE braqui_posicion_inicial SET version_algoritmo = 'PI-1' WHERE id = ?", (id_registro,))
        assert set(bp.tablas_del_mensual(FECHA_DIARIO, SERIE_A)) == {bp.CLAVE_SECCION}
        diario = bp.bloque_del_diario(FECHA_DIARIO)
        assert diario["png"] is None and ("Perfil", svc.FRASE_OTRA_VERSION.format(guardada="PI-1", actual=motor.VERSION_ALGORITMO)) in diario["filas"]

    def test_un_error_al_dibujar_no_tumba_nada_sale_con_lo_guardado_la_frase_sin_texto_tecnico_y_el_detalle_en_el_registro(self, bd, monkeypatch, tmp_path):
        """M17: el `try` del dibujo. Un error al componer la figura NO tumba el PDF."""
        _guardado(bd)
        registro = _error_log(monkeypatch, tmp_path)

        def revienta(*a, **k):
            raise RuntimeError("matplotlib se rompio dibujando")

        monkeypatch.setattr(_modulo_bp(), "png_del_perfil", revienta)
        diario = bp.bloque_del_diario(FECHA_DIARIO)
        assert diario["png"] is None and ("Perfil", svc.FRASE_NO_SE_PUDO_DIBUJAR) in diario["filas"] and diario["linea"].startswith("Capa verde: ")
        assert "matplotlib se rompio" not in "".join(v for _, v in diario["filas"]), "el detalle tecnico no va al documento"
        assert "matplotlib se rompio dibujando" in registro.read_text(encoding="utf-8") and "B.6" in registro.read_text(encoding="utf-8")
        assert set(bp.tablas_del_mensual(FECHA_DIARIO, SERIE_A)) == {bp.CLAVE_SECCION}

    def test_un_fallo_de_la_base_sube_no_se_disfraza_de_error_de_dibujo(self, bd, monkeypatch):
        _guardado(bd)
        monkeypatch.setattr(svc, "bloque_para_pdf", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        with pytest.raises(sqlite3.OperationalError):
            bp.bloque_del_diario(FECHA_DIARIO)
        with pytest.raises(sqlite3.OperationalError):
            bp.tablas_del_mensual(FECHA_DIARIO, SERIE_A)


# ----------------------------------------------------------------------------------------------- un registro sin capa y la constante por omision

from test_pi8_pdf_diario_posicion_inicial import (ALTO_PAGINA, CARGO, TEXTO_LARGO, Y_MAXIMO_DEL_CONTENIDO, _bloque, _cabecera, _df_rapido, _pdf,  # noqa: E402,F401
                                                  FILAS_TIPICAS)


def _figuras_de(pdf):
    """Los pixeles (RGB) de cada imagen de 420 x 400 pt del PDF: lo que se ve de la figura, para comparar dos PDF sin depender de como reportlab recomprime el PNG."""
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        salida = []
        for _, _, xref, _, _ in _figuras(pdf):
            salida.append(np.asarray(Image.open(io.BytesIO(doc.extract_image(xref)["image"])).convert("RGB")))
        return salida
    finally:
        doc.close()


class TestUnRegistroSinCapaSeImprimeComoHoyConElGris:
    """B6-F4: un registro sin capa (anterior a B.5, o guardado por la pagina de antes de B.7, que no la pasaba) se imprime como bloque del gris con su figura, y el bloque lo dice."""

    def test_el_diario(self, app, bd_temporal, monkeypatch):
        _sembrar_diario(bd_temporal, None)
        pdf = _pdf_diario(monkeypatch)
        texto = _normal(_texto(pdf))
        s = motor.resumen(_analisis(), "gris")
        de_siempre = f"{_n(s['desfase_fisico_mm'], 2)} ± {_n(s['U_mm'], 2)} mm (k = 2), {s['sentido']}. {s['veredicto']} (tolerancia 1.0 mm). Cambio de fuente del {S1}"
        assert de_siempre in texto and "Capa " not in texto.replace("Capa reportada", ""), "el texto es el de siempre, sin nombre de capa"
        assert "perfil de grises (el registro no guardó la capa reportada)" in texto
        propios = _numeros_de("gris")
        for clave in ("mediana", "media", "desviacion"):
            assert all(_aparece(numero, texto) for numero in propios[clave])
        figuras = _figuras_de(pdf)
        assert len(figuras) == 1
        esperada = np.asarray(Image.open(io.BytesIO(bp.png_del_perfil(_analisis(), "gris"))).convert("RGB"))
        np.testing.assert_array_equal(figuras[0], esperada)

    def test_el_mensual_la_fila_dice_lo_de_siempre(self, rm, bd, monkeypatch):
        _sembrar_mensual(bd, None)
        texto = _normal(_texto(_pdf_mensual(rm, bd, S1, "Cambio de fuente", monkeypatch)))
        s = motor.resumen(_analisis(), "gris")
        de_siempre = f"{_n(s['desfase_fisico_mm'], 2)} ± {_n(s['U_mm'], 2)} mm (k = 2), {s['sentido']}. {s['veredicto']} (tolerancia 1.0 mm). Cambio de fuente del {S1}"
        assert texto.split(ETIQUETA_DE_LA_FILA, 1)[1].startswith(" " + de_siempre), "la fila queda exactamente como hoy"
        assert "perfil de grises (el registro no guardó la capa reportada)" in texto and len(_figuras(_pdf_mensual(rm, bd, S1, "Cambio de fuente", monkeypatch))) == 1
        assert NOMBRE_DE_PERFIL["gris"] in texto and "(la reportada)" not in texto, "sin capa guardada, la tabla de la figura dice solo «Perfil de grises»: ninguna capa es «la reportada»"


class TestCambiarLaCapaPorOmisionNoCambiaNingunPdf:
    """DA-85: `CAPA_POR_OMISION` es solo el valor con que arranca el menu de la pagina; cada PDF imprime la capa que guardo su registro y nunca lee la constante (M5)."""

    @pytest.mark.parametrize("otra", ["R", "B"])
    def test_el_diario(self, app, bd_temporal, monkeypatch, otra):
        import analisisImagenes.pelicula as pelicula
        _sembrar_diario(bd_temporal, "G")
        antes = _pdf_diario(monkeypatch)
        assert pelicula.CAPA_POR_OMISION == "G"
        monkeypatch.setattr(pelicula, "CAPA_POR_OMISION", otra)
        despues = _pdf_diario(monkeypatch)
        assert _normal(_texto(antes)) == _normal(_texto(despues)) and "Capa verde" in _normal(_texto(despues))
        for a, b in zip(_figuras_de(antes), _figuras_de(despues)):
            np.testing.assert_array_equal(a, b)

    @pytest.mark.parametrize("otra", ["R", "B"])
    def test_el_mensual(self, rm, bd, monkeypatch, otra):
        import analisisImagenes.pelicula as pelicula
        _sembrar_mensual(bd, "G")
        antes = _pdf_mensual(rm, bd, S1, "Cambio de fuente", monkeypatch)
        monkeypatch.setattr(pelicula, "CAPA_POR_OMISION", otra)
        despues = _pdf_mensual(rm, bd, S1, "Cambio de fuente", monkeypatch)
        assert _normal(_texto(antes)) == _normal(_texto(despues)) and "Capa verde" in _normal(_texto(despues))
        for a, b in zip(_figuras_de(antes), _figuras_de(despues)):
            np.testing.assert_array_equal(a, b)


class TestLaFiguraDelPdfEsLaDeLaCapa:
    """M3: la imagen EMBEBIDA en el PDF es la figura de la capa guardada (pixel a pixel) y no la de otra."""

    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_diario(self, app, bd_temporal, monkeypatch, capa):
        _sembrar_diario(bd_temporal, capa)
        figuras = _figuras_de(_pdf_diario(monkeypatch))
        assert len(figuras) == 1
        esperada = np.asarray(Image.open(io.BytesIO(bp.png_del_perfil(_analisis(), capa))).convert("RGB"))
        np.testing.assert_array_equal(figuras[0], esperada)
        for otra in (p for p in PERFILES if p != capa):
            ajena = np.asarray(Image.open(io.BytesIO(bp.png_del_perfil(_analisis(), otra))).convert("RGB"))
            assert not np.array_equal(figuras[0], ajena), f"la prueba no distingue la figura de {capa} de la de {otra}"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_mensual(self, rm, bd, monkeypatch, capa):
        _sembrar_mensual(bd, capa)
        figuras = _figuras_de(_pdf_mensual(rm, bd, S1, "Cambio de fuente", monkeypatch))
        assert len(figuras) == 1
        np.testing.assert_array_equal(figuras[0], np.asarray(Image.open(io.BytesIO(bp.png_del_perfil(_analisis(), capa))).convert("RGB")))


class TestLosPdfConLoGuardadoCuandoNoSeDibuja:
    """La version distinta o el fallo al dibujar no quitan nada de lo impreso: la linea y las medidas son las guardadas, la fila «Perfil» dice por que no hay figura y el PDF SALE."""

    @pytest.mark.parametrize("version", ["PI-1", ""], ids=["anterior", "vacia"])
    def test_otra_version_el_diario_imprime_lo_guardado_dice_la_frase_y_no_lleva_ninguna_imagen_y_cero_analisis(self, app, bd_temporal, monkeypatch, version):
        id_registro = _sembrar_diario(bd_temporal, "G")
        bd_temporal.con.execute("UPDATE braqui_posicion_inicial SET version_algoritmo = ? WHERE id = ?", (version, id_registro))
        bd_temporal.con.commit()
        llamadas = _cuenta_los_analisis(monkeypatch)
        pdf = _pdf_diario(monkeypatch)
        texto = _normal(_texto(pdf))
        assert llamadas == [] and _figuras(pdf) == []
        assert _linea_esperada("G") in texto
        assert _normal(svc.FRASE_OTRA_VERSION.format(guardada=version or "sin dato", actual=motor.VERSION_ALGORITMO)) in texto
        for clave, (mm, px) in ((c, _numeros_de("G")[c]) for c in ("mediana", "media", "desviacion")):
            assert _aparece(mm, texto) and _aparece(px, texto)

    def test_otra_version_el_mensual_lleva_la_seccion_sin_grafico(self, rm, bd, monkeypatch):
        _, _ = _sembrar_mensual(bd, "G")
        _sql(bd, "UPDATE braqui_posicion_inicial SET version_algoritmo = 'PI-1'")
        llamadas = _cuenta_los_analisis(monkeypatch)
        pdf = _pdf_mensual(rm, bd, S1, "Cambio de fuente", monkeypatch)
        texto = _normal(_texto(pdf))
        assert llamadas == [] and _figuras(pdf) == [] and texto.count(TITULO) == 1
        assert _normal(svc.FRASE_OTRA_VERSION.format(guardada="PI-1", actual=motor.VERSION_ALGORITMO)) in texto and _linea_esperada("G") in texto

    def test_la_imagen_corrupta_el_diario_sale_con_lo_guardado_y_el_detalle_en_el_registro(self, app, bd_temporal, monkeypatch, tmp_path):
        id_registro = _sembrar_diario(bd_temporal, "G")
        bd_temporal.con.execute("UPDATE braqui_posicion_inicial SET imagen = ? WHERE id = ?", (b"no es una imagen", id_registro))
        bd_temporal.con.commit()
        registro = _error_log(monkeypatch, tmp_path)
        pdf = _pdf_diario(monkeypatch)
        texto = _normal(_texto(pdf))
        assert _figuras(pdf) == [] and _linea_esperada("G") in texto and _normal(svc.FRASE_NO_SE_PUDO_MEDIR) in texto
        assert "B.6" in registro.read_text(encoding="utf-8")

    def test_un_error_al_dibujar_el_diario_sale_con_lo_guardado_la_frase_y_el_detalle_en_el_registro(self, app, bd_temporal, monkeypatch, tmp_path):
        """M17: sin el `try` del dibujo un error tumbaria el PDF."""
        _sembrar_diario(bd_temporal, "G")
        registro = _error_log(monkeypatch, tmp_path)
        monkeypatch.setattr(_modulo_bp(), "png_del_perfil", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fallo al rasterizar")))
        pdf = _pdf_diario(monkeypatch)
        texto = _normal(_texto(pdf))
        assert _figuras(pdf) == [] and _linea_esperada("G") in texto and _normal(svc.FRASE_NO_SE_PUDO_DIBUJAR) in texto and "fallo al rasterizar" not in texto
        assert "fallo al rasterizar" in registro.read_text(encoding="utf-8")

    def test_un_error_al_dibujar_el_mensual_sale_con_la_seccion_y_sin_el_grafico(self, rm, bd, monkeypatch, tmp_path):
        _sembrar_mensual(bd, "G")
        registro = _error_log(monkeypatch, tmp_path)
        monkeypatch.setattr(_modulo_bp(), "png_del_perfil", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fallo al rasterizar")))
        pdf = _pdf_mensual(rm, bd, S1, "Cambio de fuente", monkeypatch)
        texto = _normal(_texto(pdf))
        assert _figuras(pdf) == [] and _normal(svc.FRASE_NO_SE_PUDO_DIBUJAR) in texto and _linea_esperada("G") in texto and registro.exists()

    def test_un_fallo_de_la_base_el_diario_avisa_y_no_genera(self, app, bd_temporal, monkeypatch):
        """Regla de PI.8: la base que falla no produce un bloque dudoso: el aviso dice la causa y el PDF no sale."""
        _sembrar_diario(bd_temporal, "G")
        avisos, visores = [], []
        monkeypatch.setattr(svc, "leer", lambda identificador: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: avisos.append(a)))

        class _Visor:
            def __init__(self, *a, **k):
                visores.append(1)

            def show(self):
                visores.append(1)

        monkeypatch.setattr(reportes_mod, "PdfViewer", _Visor)
        reportes_mod.reporte(_AutoDB(), fecha=FECHA_DIARIO, maquina="Gammamed Plus i X", id_maquina="", tipo_reporte="diario", diccionario=DICC_BRAQUI, umbrales="si", file_name="")
        assert visores == [] and len(avisos) == 1 and "database is locked" in avisos[0][2]


# ------------------------------------------------------------------------------------------------------------------ la paginacion del diario

def _png_de_relleno():
    """Un PNG de 84 x 80 px: el generador mide la figura por `ancho_pt` y `alto_pt` (420 x 400), no por sus pixeles, asi que el barrido de paginacion usa uno pequeno (rapido) y la figura real se prueba aparte."""
    buffer = io.BytesIO()
    Image.new("RGB", (84, 80), (200, 220, 240)).save(buffer, "PNG")
    return buffer.getvalue()


def _bloque_del_diario(linea=None, filas=None, png=True):
    bloque = _bloque(linea if linea is not None else "Capa verde: -0.10 ± 0.16 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm). Cambio de fuente del 2026-01-10", filas=filas)
    bloque["png"] = _png_de_relleno() if png else None
    return bloque


LINEA_MAS_LARGA = "Capa verde: " + TEXTO_LARGO


def _filas_todas():
    """Las seis filas de siempre mas la de «Perfil» (la frase mas larga de las que la explican). Se arma al usarla y no al importar: contra el servicio de HEAD (que no tiene `FRASE_OTRA_VERSION`) el
    archivo tiene que seguir importandose, para que el rojo sea el de cada prueba y no el de la coleccion."""
    return FILAS_TIPICAS + [("Perfil", svc.FRASE_OTRA_VERSION.format(guardada="una versión muy anterior del algoritmo", actual=motor.VERSION_ALGORITMO))]


def _revisar_el_bloque(doc, r6, con_figura=True):
    """Todo lo que el plan exige del bloque (tabla + figura) sobre un PDF real; devuelve (pagina de la tabla, pagina de R6 o None)."""
    titulos = [(i, r) for i, pagina in enumerate(doc) for r in pagina.search_for(TITULO)]
    assert len(titulos) == 1, f"el bloque debe salir UNA vez, salio {len(titulos)}"
    pagina, rect = titulos[0]
    _, banda = _cabecera(doc, TITULO)
    assert abs(banda.x0 - 81) < 0.6 and abs(banda.x1 - (81 + 450)) < 0.6, f"la tabla del bloque debe medir los 450 pt de la tabla principal (la cabecera va de x={banda.x0:.1f} a x={banda.x1:.1f}) (M45)"
    figuras = [im for im in _imagenes(doc.tobytes()) if abs(im[1].width - ANCHO_FIGURA_PT) < 1 and abs(im[1].height - ALTO_FIGURA_PT) < 1]
    if con_figura:
        assert len(figuras) == 1, f"el bloque debe llevar UNA figura de 420 x 400 pt (hay {len(figuras)})"
        pagina_figura, rect_figura = figuras[0][0], figuras[0][1]
        assert pagina_figura == pagina, "la figura debe salir en la MISMA pagina que su tabla (M10: un salto por pieza la deja lejos)"
        assert rect_figura.y0 >= rect.y1, "la figura va DEBAJO de su tabla"
        assert rect_figura.y1 <= Y_MAXIMO_DEL_CONTENIDO + 0.5, f"la figura invade la franja de la firma (y1={rect_figura.y1:.1f}, limite {Y_MAXIMO_DEL_CONTENIDO})"
        assert abs((rect_figura.x0 + rect_figura.x1) / 2 - (81 + 450 / 2)) < 1, "la figura va centrada bajo los 450 pt de la tabla"
    else:
        assert figuras == []
    # la tabla del bloque tampoco invade la franja de la firma
    trazos = [d["rect"] for d in doc[pagina].get_drawings() if d["rect"].y0 >= rect.y0 - 6 and d["rect"].y1 < ALTO_PAGINA - 60 and d["rect"].width > 5]
    assert max(r.y1 for r in trazos) <= Y_MAXIMO_DEL_CONTENIDO + 0.5
    pagina_r6 = None
    if r6 != "sin":
        encontrados = [(i, r) for i, p in enumerate(doc) for r in p.search_for("Análisis de la placa")]
        assert len(encontrados) == 1
        pagina_r6 = encontrados[0][0]
        assert (pagina, rect.y0) > (pagina_r6, encontrados[0][1].y0), "el bloque va DESPUES de R6"
    # la firma, UNA vez en cada pagina
    for i, p in enumerate(doc):
        assert p.get_text().count(CARGO) == 1, f"la pagina {i} de {doc.page_count} tiene el bloque de firma {p.get_text().count(CARGO)} veces"
    return pagina, pagina_r6


class TestElBloqueEsUnaUnidadQueSaltaEnteroYNuncaPisaLaFirma:
    @pytest.mark.parametrize("r6", ["sin", "sin_pelicula", "con_pelicula"])
    @pytest.mark.parametrize("nombre,linea", [("tipica", None), ("la_mas_larga", LINEA_MAS_LARGA)])
    def test_de_0_a_70_filas_la_tabla_y_la_figura_salen_juntas_una_vez_sin_invadir_la_firma(self, app, r6, nombre, linea):
        paginas_del_bloque, mismas_que_r6, despues_de_r6, en_pagina_nueva = set(), 0, 0, 0
        for n in range(0, 71, 2):
            doc = fitz.open(stream=_pdf(_df_rapido(n, r6), _bloque_del_diario(linea)), filetype="pdf")
            try:
                pagina, pagina_r6 = _revisar_el_bloque(doc, r6)
                paginas_del_bloque.add(doc.page_count)
                if pagina_r6 is not None:
                    mismas_que_r6 += pagina == pagina_r6
                    despues_de_r6 += pagina > pagina_r6
                en_pagina_nueva += not any(p.search_for("Prueba número") for p in [doc[pagina]])
            finally:
                doc.close()
        assert len(paginas_del_bloque) >= 2, "el barrido no llego a producir PDF de distinto numero de paginas: no discrimina"
        assert en_pagina_nueva >= 1, "ninguna colocacion hizo saltar el bloque a una pagina sin filas de la tabla principal"
        if r6 != "sin":
            assert despues_de_r6 >= 1, "el barrido tiene que recorrer el caso en que el bloque no cabe bajo R6 y salta (Trampa 8)"

    def test_el_bloque_mas_grande_cabe_siempre_en_una_pagina_vacia(self, app):
        """«Cabe siempre en una pagina vacia»: la linea mas larga y todas las filas (hasta «Perfil» con su frase) -sin figura- y la linea mas larga con las filas y la figura de 400 pt: tabla + figura + 20 <= 617 pt (742 - 125)."""
        for con_figura in (True, False):
            filas = FILAS_TIPICAS if con_figura else _filas_todas()
            doc = fitz.open(stream=_pdf(_df_rapido(0, "sin"), _bloque_del_diario(LINEA_MAS_LARGA, filas=filas, png=con_figura)), filetype="pdf")
            try:
                pagina, _ = _revisar_el_bloque(doc, "sin", con_figura=con_figura)
                _, rect = _cabecera(doc, TITULO)
                fondo = max(r.y1 for r in [d["rect"] for d in doc[pagina].get_drawings() if d["rect"].y0 >= rect.y0 - 6 and d["rect"].y1 < ALTO_PAGINA - 60 and d["rect"].width > 5])
                fondo = max(fondo, *[im[1].y1 for im in _imagenes(doc.tobytes()) if im[0] == pagina and abs(im[1].height - ALTO_FIGURA_PT) < 1] or [0])
                assert fondo - rect.y0 <= 617 - 20 + 0.5, f"el bloque mide {fondo - rect.y0:.1f} pt (limite 617 con sus dos separaciones)"
            finally:
                doc.close()

    def test_un_texto_con_marcas_de_xml_se_imprime_tal_cual_y_no_tumba_el_diario(self, app):
        """M68/M69: los textos del bloque van en un `Paragraph`, que los lee como marcado: un `<` o un `&` en la linea o en una fila (el motivo de un registro, una frase, una serie) tumbaria la generacion de TODO
        el diario, o se tragaria el texto entre marcas, si no se escaparan. Se imprimen tal cual."""
        linea = "Capa verde: -0.10 mm; si a < b & c > d <b>no es negrita</b>"
        filas = [("Capa reportada", "capa verde"), ("Rotulo con & y <", "valor con <i>marcas</i> & mas")]
        texto = _normal(_texto(_pdf(_df_rapido(0, "sin"), _bloque_del_diario(linea, filas=filas, png=False))))
        for esperado in ("si a < b & c > d <b>no es negrita</b>", "Rotulo con & y <", "valor con <i>marcas</i> & mas"):
            assert esperado in texto, f"el PDF no dice {esperado!r}"

    def test_un_bloque_con_figura_es_una_sola_llamada_a_la_regla_de_salto(self):
        """M10: la regla de salto se llama UNA vez para el bloque (tabla + figura juntas): una llamada por pieza la deja saltar entre las dos."""
        import ast
        import inspect
        import models.PDF.pdf as pdf_mod
        arbol = ast.parse(inspect.getsource(pdf_mod.generar_reporte_pdf))
        bloque = next(n for n in ast.walk(arbol) if isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name) and n.test.left.id == "posicion_inicial")
        llamadas = [c for c in ast.walk(bloque) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "_salto_si_no_cabe"]
        assert len(llamadas) == 1, f"el bloque llama {len(llamadas)} veces a la regla de salto (debe ser una, con la altura de la tabla y la figura juntas)"


# ---------------------------------------------------------------------------------------------------------- tripwires por AST: capas, imports, mudanza

import ast                                                              # noqa: E402
import subprocess                                                       # noqa: E402
import sys                                                              # noqa: E402
from pathlib import Path                                                # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SERVICIO_PY = "services/posicion_inicial_braqui.py"
REPORTES_PY = "models/PDF/reportes.py"
PDF_PY = "models/PDF/pdf.py"
MENSUALES_PY = "models/PDF/Mensuales/reportes_mensuales.py"
BLOQUE_PY = "models/PDF/bloque_posicion_inicial.py"
DIBUJO_PY = "analisisImagenes/dibujo_posicion_inicial.py"
PAGINA_PY = "ui/paginasControles/PruebasMensuales/posicion_inicial_braqui.py"
SECCION_MENSUAL_PY = "models/PDF/Mensuales/seccion_placa_mensual.py"            # F.1: el PDF del mensual del 600 y del iX imprime la capa que guardo el registro (la seccion y la pelicula con su recuadro)
PELICULA_CON_RECUADRO_PY = "models/PDF/Mensuales/pelicula_con_recuadro.py"
DONDE_NO_SE_ELIGE_LA_CAPA_A_MANO = (SERVICIO_PY, REPORTES_PY, PDF_PY, MENSUALES_PY, BLOQUE_PY, SECCION_MENSUAL_PY, PELICULA_CON_RECUADRO_PY)
# Las UNICAS excepciones, cada una con su motivo: los nombres de columna de la tabla del servicio (`desfase_g_px`, `desfase_g_mm`...: son columnas, no una eleccion de capa; mientras sigan escritos
# asi) y el especificador de formato `{valor:g}` de un f-string (el `g` de «general», no la capa verde).
ASIGNACIONES_CON_COLUMNAS_PERMITIDAS = {"_COLUMNAS_SQL", "_COLUMNAS_INSERT"}


def _fuente(ruta):
    return (RAIZ / ruta).read_text(encoding="utf-8")


def capas_escritas_a_mano(texto):
    """[(linea, texto)] de las cadenas que ESCRIBEN una capa a mano: una letra `r`, `g` o `b` sola (en cualquier capitalizacion), un nombre de color (rojo, roja, verde, azul) o una plantilla `_g_`. No cuentan
    los docstrings, el especificador de formato de un f-string ni las asignaciones declaradas de columnas."""
    arbol = ast.parse(texto)
    excluidos = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant):
            excluidos.add(id(n.value))                                                  # docstrings y cadenas sueltas
        if isinstance(n, ast.FormattedValue) and n.format_spec is not None:
            excluidos.update(id(x) for x in ast.walk(n.format_spec))                    # `{valor:g}`
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ASIGNACIONES_CON_COLUMNAS_PERMITIDAS for t in n.targets):
            excluidos.update(id(x) for x in ast.walk(n.value))
    hallados = []
    for n in ast.walk(arbol):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in excluidos:
            v = n.value
            if v.strip().lower() in ("r", "g", "b") or re.search(r"_[rgb]_|(?<![A-Za-z])(rojo|roja|verde|azul)(?![A-Za-z])", v, re.IGNORECASE):
                hallados.append((n.lineno, v[:60]))
    return hallados


def lee_capa_por_omision(texto):
    """[linea] donde el codigo nombra `CAPA_POR_OMISION` (un nombre, un atributo o un import)."""
    arbol = ast.parse(texto)
    return sorted({n.lineno for n in ast.walk(arbol) if (isinstance(n, ast.Name) and n.id == "CAPA_POR_OMISION") or (isinstance(n, ast.Attribute) and n.attr == "CAPA_POR_OMISION")
                   or (isinstance(n, ast.ImportFrom) and any(a.name == "CAPA_POR_OMISION" for a in n.names))})


class TestNingunaCapaEscritaAManoNiLeidaDeLaConstante:
    @pytest.mark.parametrize("ruta", DONDE_NO_SE_ELIGE_LA_CAPA_A_MANO)
    def test_ninguna_capa_escrita_a_mano(self, ruta):
        """M1: ni «G», ni «verde», ni `_g_`, ni las otras dos: la capa sale del registro (`capa_del_registro`), de `pelicula.CAPAS` y de `NOMBRE_DE_CAPA`."""
        assert capas_escritas_a_mano(_fuente(ruta)) == [], f"{ruta} escribe una capa a mano"

    @pytest.mark.parametrize("ruta", DONDE_NO_SE_ELIGE_LA_CAPA_A_MANO)
    def test_ningun_pdf_ni_el_servicio_lee_capa_por_omision(self, ruta):
        """M5: la constante es solo el valor con que arranca el menu de la pagina."""
        assert lee_capa_por_omision(_fuente(ruta)) == [], f"{ruta} lee CAPA_POR_OMISION"

    @pytest.mark.parametrize("ruta", DONDE_NO_SE_ELIGE_LA_CAPA_A_MANO)
    @pytest.mark.parametrize("inyeccion", ['capa = "G"', "capa = 'g'", 'nombre = "verde"', 'columna = "estado_g"[:-1] + "_g_px"', 'x = "B"', 'color = "rojo"'])
    def test_discrimina_cada_forma_de_escribir_una_capa_en_cada_archivo(self, ruta, inyeccion):
        assert capas_escritas_a_mano(_fuente(ruta) + f"\n\ndef _por_comodidad():\n    {inyeccion}\n    return 1\n"), f"el guardia no ve: {inyeccion}"

    @pytest.mark.parametrize("ruta", DONDE_NO_SE_ELIGE_LA_CAPA_A_MANO)
    @pytest.mark.parametrize("inyeccion", ["from analisisImagenes.pelicula import CAPA_POR_OMISION", "import analisisImagenes.pelicula as p\nx = p.CAPA_POR_OMISION", "x = CAPA_POR_OMISION"])
    def test_discrimina_cada_forma_de_leer_la_constante(self, ruta, inyeccion):
        assert lee_capa_por_omision(inyeccion + "\n" + _fuente(ruta)), f"el guardia no ve: {inyeccion}"

    def test_las_excepciones_declaradas_son_reales_y_no_dejan_pasar_otra_cosa(self):
        """No vacuidad: las dos excepciones existen (si ya no estuvieran, la lista estaria declarando de mas) y un `g` suelto fuera de ellas se ve."""
        assert "desfase_g_px" in _fuente(SERVICIO_PY) and ":g}" in _fuente(SERVICIO_PY) and ":g}" in _fuente(BLOQUE_PY)
        sin_excepcion = _fuente(SERVICIO_PY).replace("_COLUMNAS_SQL = (", "_otra_cosa = (", 1)
        assert capas_escritas_a_mano(sin_excepcion), "al quitar la excepcion de las columnas, el guardia debia ver las plantillas `_g_`"

    # R1P-03 (revision, ronda 1): aqui habia una prueba que buscaba `capa.lower()` y `s = capa.lower()` en el TEXTO del servicio. Vigilaba la forma de escribir el codigo (un refactor equivalente la
    # rompia) y no la garantia, que es de comportamiento: la cubre `TestCadaPerfilLeeSusSieteColumnasYNingunaDeOtro` (con la mutacion que la hace caer en `b6_mutaciones.py`) y que ningun codigo
    # escriba la letra de una capa lo vigila `test_ninguna_capa_escrita_a_mano`, de arriba.


# --------------------------------------------------------------------------- R1-PROD-01: el nombre de una capa en una frase es UNO y concuerda con «capa»

TABLAS_DE_LOS_COLORES = frozenset({"NOMBRE_DE_CAPA", "_NOMBRE_DE_LA_CAPA_DEL_PISO"})        # los colores a secas (rojo, verde, azul: masculinos; para los menus y para «el rojo»), no para «capa ...»
EXCLUIDOS_DE_PRODUCCION = {".venv", "build", "dist", "tests", "__pycache__", ".git", "node_modules", ".pytest_cache"}


def _usa_la_tabla_de_los_colores(nodo):
    return any((isinstance(n, ast.Name) and n.id in TABLAS_DE_LOS_COLORES) or (isinstance(n, ast.Attribute) and n.attr in TABLAS_DE_LOS_COLORES) for n in ast.walk(nodo))


def _es_texto_que_dice(nodo, patron):
    return isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and re.search(patron, nodo.value, re.IGNORECASE) is not None


def frases_con_capa_y_un_color_sin_concordar(texto):
    """[(linea, forma)] de las frases que dicen «capa» seguido de un color tomado de la tabla de los COLORES (`NOMBRE_DE_CAPA`: rojo, verde, azul, masculinos, para los menus): «capa rojo» no concuerda
    con el sustantivo femenino. Formas: un f-string («capa {NOMBRE_DE_CAPA[c]}»), una suma, `%`, `.format` y la frase escrita tal cual («capa rojo»). No cuentan los docstrings."""
    arbol = ast.parse(texto)
    docstrings = {id(n.value) for n in ast.walk(arbol) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    hallados = []
    for n in ast.walk(arbol):
        if isinstance(n, ast.JoinedStr):
            hallados += [(n.lineno, "f-string") for anterior, siguiente in zip(n.values, n.values[1:])
                         if _es_texto_que_dice(anterior, r"\bcapa\s*$") and isinstance(siguiente, ast.FormattedValue) and _usa_la_tabla_de_los_colores(siguiente.value)]
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add) and _es_texto_que_dice(n.left, r"\bcapa\s*$") and _usa_la_tabla_de_los_colores(n.right):
            hallados.append((n.lineno, "suma"))
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and _es_texto_que_dice(n.left, r"\bcapa\s+%[sd]") and _usa_la_tabla_de_los_colores(n.right):
            hallados.append((n.lineno, "%"))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "format" and _es_texto_que_dice(n.func.value, r"\bcapa\s+\{") \
                and any(_usa_la_tabla_de_los_colores(a) for a in [*n.args, *[k.value for k in n.keywords]]):
            hallados.append((n.lineno, "format"))
        elif isinstance(n, ast.Constant) and id(n) not in docstrings and _es_texto_que_dice(n, r"\bcapa\s+rojo\b"):
            hallados.append((n.lineno, "escrito tal cual"))
    return hallados


def _produccion():
    """{ruta relativa: texto} de todo el codigo de produccion (el mismo arbol que recorre el tripwire de PI.10)."""
    fuentes = {}
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in EXCLUIDOS_DE_PRODUCCION]
        for nombre in archivos:
            if nombre.endswith(".py"):
                ruta = Path(carpeta) / nombre
                fuentes[str(ruta.relative_to(RAIZ)).replace(os.sep, "/")] = ruta.read_text(encoding="utf-8", errors="replace")
    return fuentes


class TestNingunaFraseDiceCapaYUnColorSinConcordar:
    """R1-PROD-01 (revision, ronda 1): los dos PDF decian «Capa rojo: ...» y «capa rojo» (la fila «Capa reportada») porque armaban la frase con `NOMBRE_DE_CAPA` -la tabla de los colores de los menus: rojo,
    verde, azul- detras de la palabra femenina «capa»; la figura del mismo bloque decia «Capa roja». Dos nombres de la misma capa en un documento firmado, uno con la concordancia equivocada, y las pruebas
    usaban la propia constante como oraculo. Era la MISMA clase de error de un texto de A.3 («el piso de la capa rojo no es mas claro...»): la causa es que la tabla que concuerda existia solo como un
    detalle privado de `pelicula.py`. Ahora es una (`ADJETIVO_DE_LA_CAPA`) y este tripwire vigila TODO el codigo de produccion, no los sitios que se encontraron."""

    def test_en_todo_el_codigo_de_produccion_ninguna_frase_dice_capa_y_el_color_de_los_menus(self):
        fuentes = _produccion()
        assert len(fuentes) >= 100 and {SERVICIO_PY, BLOQUE_PY, "analisisImagenes/pelicula.py", PAGINA_PY} <= set(fuentes), f"no vacuidad: solo se leyeron {len(fuentes)} archivos"
        malos = {}
        for ruta, texto in fuentes.items():
            try:
                hallados = frases_con_capa_y_un_color_sin_concordar(texto)
            except SyntaxError:
                continue
            if hallados:
                malos[ruta] = hallados
        assert not malos, f"frases con «capa» y el color de los menus (no concuerdan: «capa rojo»); usen `pelicula.ADJETIVO_DE_LA_CAPA`: {malos}"

    @pytest.mark.parametrize("inyeccion", [
        'x = f"Capa {NOMBRE_DE_CAPA[c]}: algo"',
        'x = f"la capa {pelicula.NOMBRE_DE_CAPA[c]} no"',
        'x = f"el piso de la capa {_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} no es mas claro"',
        'x = "capa " + NOMBRE_DE_CAPA[c]',
        'x = "capa {}".format(NOMBRE_DE_CAPA[c])',
        'x = "capa %s" % NOMBRE_DE_CAPA[c]',
        'x = "la capa rojo"',
        'x = "Capa Rojo: "'])
    def test_el_guardia_ve_cada_forma_de_armar_la_frase(self, inyeccion):
        assert frases_con_capa_y_un_color_sin_concordar(inyeccion + "\n"), f"el guardia no ve: {inyeccion}"

    @pytest.mark.parametrize("correcto", [
        'x = f"el {NOMBRE_DE_CAPA[c]}"',
        'x = f"{NOMBRE_DE_CAPA[c]} 12"',
        'x = [NOMBRE_DE_CAPA[c] for c in CAPAS]',
        'x = f"capa {ADJETIVO_DE_LA_CAPA[c]}"',
        'x = f"Capa {c}"',
        'x = "capa roja"',
        'x = "capa verde"',
        'def f():\n    """La capa rojo es un error comun."""\n    return 1'])
    def test_el_guardia_no_marca_lo_que_concuerda_ni_los_colores_a_secas_ni_los_docstrings(self, correcto):
        assert frases_con_capa_y_un_color_sin_concordar(correcto + "\n") == [], f"el guardia marca de mas: {correcto}"


class TestElNombreDeLaCapaEnUnaFraseEsUnoSolo:
    """La tabla que concuerda (`pelicula.ADJETIVO_DE_LA_CAPA`), el titulo de la figura (`NOMBRE_DE_PERFIL`, mudado de la pagina con su cuerpo sin cambiar), la linea y la fila del bloque dicen lo mismo."""

    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_tabla_que_concuerda_el_titulo_de_la_figura_la_linea_y_la_fila_dicen_lo_mismo(self, capa):
        from analisisImagenes import pelicula as pel
        frase = CAPA_EN_UNA_FRASE[capa]
        assert pel.ADJETIVO_DE_LA_CAPA[capa] == frase.split()[1], "la tabla que concuerda"
        assert NOMBRE_DE_PERFIL[capa] == frase.capitalize(), "el titulo de la figura es la misma frase (convergencia de dos definiciones, afirmada con una prueba)"
        registro = _registro_con_las_cuatro_medidas(capa, version_algoritmo="OTRA")
        assert svc.bloque_pdf_posicion_inicial(registro)["linea"].startswith(frase.capitalize() + ": ")
        assert dict(bp.filas_del_bloque(svc.bloque_pdf_posicion_inicial(registro)))["Capa reportada"] == frase

    def test_las_dos_tablas_son_la_de_los_colores_de_los_menus_y_la_que_concuerda_con_capa(self):
        """Los menus «Capa reportada» (B.7, E.1) y la columna «Capa» de la tabla de registros dicen el color a secas; toda frase con «capa» usa la otra (el tripwire de arriba lo vigila)."""
        from analisisImagenes import pelicula as pel
        assert pel.NOMBRE_DE_CAPA == {"R": "rojo", "G": "verde", "B": "azul"}, "los menus «Capa reportada» (B.7, E.1) y la columna «Capa» de la tabla de registros dicen el color a secas"
        assert pel.ADJETIVO_DE_LA_CAPA == {"R": "roja", "G": "verde", "B": "azul", "gris": "gris"}

    def test_el_motivo_de_una_capa_sin_contraste_del_piso_tambien_concuerda(self, monkeypatch):
        """La misma clase de error, hallada en A.3 al buscarla en todo el codigo: «el piso de la capa rojo no es mas claro que la meseta...». `_piso_capas` con una meseta simulada (cada capa a 100
        y su piso a 50: el contraste es -50, menos de los 10 niveles que se exigen)."""
        from analisisImagenes import pelicula as pel
        monkeypatch.setattr(pel, "_piso_meseta_de_referencia", lambda *a, **k: {c: 100.0 for c in pel.CAPAS_DEL_PISO})
        capas = pel._piso_capas(None, None, 25.4 / 600.0, {"contraste_minimo": 10.0}, {c: (50.0, 5000, 1.0) for c in pel.CAPAS_DEL_PISO})
        for c, frase in (("R", "capa roja"), ("G", "capa verde"), ("B", "capa azul"), ("gris", "capa gris")):
            assert capas[c].estado.startswith(f"no medible: el piso de la {frase} no es más claro que la meseta en al menos 10 niveles"), capas[c].estado


class TestLosImportsDeLasTresPiezas:
    def _importados(self, ruta):
        arbol = ast.parse(_fuente(ruta))
        modulos = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Import):
                modulos.update(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module:
                modulos.add(n.module)
                modulos.update(f"{n.module}.{a.name}" for a in n.names)
        return modulos

    def test_el_modulo_de_dibujo_no_importa_qt_ni_matplotlib(self):
        malos = {m for m in self._importados(DIBUJO_PY) if m.startswith(("PyQt", "PySide", "matplotlib", "ui.", "services", "models"))}
        assert not malos, malos

    def test_el_modulo_del_pdf_no_importa_el_motor_ni_qt_ni_pyplot(self):
        malos = {m for m in self._importados(BLOQUE_PY) if m.startswith(("PyQt", "PySide")) or m in ("matplotlib.pyplot", "analisisImagenes.posicion_inicial_braqui")}
        assert not malos, malos
        assert not [n for n in ast.walk(ast.parse(_fuente(BLOQUE_PY))) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "use"], "matplotlib.use"

    def test_el_servicio_no_dibuja_ni_importa_el_modulo_de_dibujo_ni_matplotlib_ni_qt(self):
        malos = {m for m in self._importados(SERVICIO_PY) if m.startswith(("PyQt", "PySide", "matplotlib", "reportlab", "models", "ui.")) or "dibujo_posicion_inicial" in m}
        assert not malos, malos

    def test_la_pagina_importa_los_28_nombres_del_modulo_de_dibujo_y_ya_no_define_ninguno(self):
        """«Los 28 nombres re-exportados son el mismo objeto»: `pagina_mod.X` es `dibujo.X` (B.1, B.4 y PI.4 los leen desde la pagina)."""
        import analisisImagenes.dibujo_posicion_inicial as dibujo
        nombres = ["_numero", "motivo_para_no_guardar", "fila_representativa", "_poligono", "_dibujar_bandas", "dibujar_ventana", "dibujar_perfil", "texto_de_parametros", "rotular_parametros",
                   "datos_del_barrido", "_cuantas", "texto_de_la_regla", "dibujar_barrido_de_filas", "LINEA_REFINADA", "COLOR_MEDIDO", "COLOR_REFERENCIA", "TINTA", "TINTA_SUAVE", "COLOR_CAPA",
                   "COLOR_LINEA_DESCARTADA", "COLOR_REJILLA", "NOMBRE_DE_PERFIL", "NIVEL_DE_PERFIL", "COLOR_TRANSITO", "TRAZO_DE_PARAMETRO", "LARGO_DEL_PIE", "COLOR_FILA_QUE_NO_ENTRA",
                   "ANCHO_DE_LA_LEYENDA"]
        assert len(nombres) == 28 == len(set(nombres))
        for nombre in nombres:
            assert getattr(pagina_mod, nombre) is getattr(dibujo, nombre), nombre
        arbol = ast.parse(_fuente(PAGINA_PY))
        definidos = {n.name for n in arbol.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))} | {t.id for n in arbol.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        assert not (definidos & set(nombres)), f"la pagina define de nuevo lo mudado: {sorted(definidos & set(nombres))}"
        # y lo que NO se muda se queda en la pagina (la pantalla y la imagen sintetica)
        assert {"dibujar_barrido", "ALTOS_DE_LA_PESTANA_DEL_GRIS", "ALTO_MINIMO_DEL_LIENZO", "EJES_DE_LA_PESTANA_DEL_GRIS"} <= definidos

    def test_el_modulo_de_dibujo_define_exactamente_lo_mudado(self):
        arbol = ast.parse(_fuente(DIBUJO_PY))
        funciones = [n.name for n in arbol.body if isinstance(n, ast.FunctionDef)]
        constantes = [t.id for n in arbol.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)]
        assert len(funciones) == 14 and len(constantes) == 15 and len(set(funciones)) == 14, \
            "B.7: 13 funciones mudadas de la pagina en B.6 mas `titulo_del_perfil` (el titulo de una grafica, que `dibujar_perfil` y la pagina comparten); las 15 constantes son las mismas"
        assert "titulo_del_perfil" in funciones


class TestElBackendDeMatplotlibNoCambia:
    CODIGO = (
        "import os, sys\n"
        "os.environ['QT_QPA_PLATFORM'] = 'offscreen'\n"
        "sys.path.insert(0, os.getcwd())\n"
        "import matplotlib\n"
        "antes = matplotlib.get_backend(auto_select=False)\n"             # sin resolver: `get_backend()` a secas ya importaria pyplot para elegir un backend
        "import services.posicion_inicial_braqui as svc\n"
        "from models.PDF import bloque_posicion_inicial as bp\n"
        "datos = open(os.path.join('tests', 'datos', 'braqui_00.jpeg'), 'rb').read()\n"
        "r = svc.analizar_imagen(datos, [(191, 377), (190, 56)])\n"
        "png = bp.png_del_perfil(r, 'G')\n"
        "print('RESULTADO', antes == matplotlib.get_backend(auto_select=False), 'matplotlib.pyplot' in sys.modules, len(png) > 10000)\n")

    def test_generar_la_figura_no_importa_pyplot_ni_cambia_el_backend_del_proceso(self):
        """B.6 (f): en un proceso limpio, importar el modulo y generar la figura deja el backend como estaba y no trae `pyplot` (el cargador diferido de la aplicacion y los dos graficos del mensual
        de braquiterapia SI lo traen/lo cambian: es anterior a B.6 y el codigo nuevo no lo empeora)."""
        r = subprocess.run([sys.executable, "-c", self.CODIGO], cwd=RAIZ, capture_output=True, text=True, timeout=300, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
        linea = [l for l in r.stdout.splitlines() if l.startswith("RESULTADO")]
        assert linea, r.stderr[-800:]
        assert linea[0] == "RESULTADO True False True", linea[0]


# ------------------------------------------------------------------------------------------------- el cableado del mensual (linealidad no cambia)

class TestElCableadoDelMensual:
    def test_la_seccion_se_pide_con_la_fecha_y_la_serie_de_la_calibracion(self, rm, monkeypatch):
        """DD8: el mismo `fecha` y `serie` que la fila «Desplazamiento inicial (mm)» (los de ESTA calibracion, no los de la peticion del reporte)."""
        import pandas as pd
        pedidos = []
        monkeypatch.setattr(_modulo_bp(), "tablas_del_mensual", lambda fecha, serie: (pedidos.append((fecha, serie)), {"posicion_inicial": pd.DataFrame([["a", "b"]], columns=["x", "y"])})[1])
        tablas = {"condiciones_medicion": pd.DataFrame([["Campo", "Valor"]], columns=["Condiciones de medición", ""])}
        salida = rm._con_posicion_inicial(tablas, {"fecha": "2026-01-10 15:03:03", "serie": SERIE_A})
        assert pedidos == [("2026-01-10 15:03:03", SERIE_A)] and set(salida) == {"condiciones_medicion", "posicion_inicial"}

    def test_el_reporte_de_linealidad_no_consulta_el_servicio_ni_cambia(self, rm, monkeypatch):
        """El `return` que llama a `_con_posicion_inicial` sirve tambien al reporte de linealidad (que no trae `condiciones_medicion`): devuelve las tablas tal cual y no consulta nada."""
        import pandas as pd
        monkeypatch.setattr(svc, "bloque_para_pdf", lambda *a, **k: pytest.fail("la linealidad no debe consultar la posicion inicial"))
        monkeypatch.setattr(_modulo_bp(), "tablas_del_mensual", lambda *a, **k: pytest.fail("la linealidad no debe pedir la seccion"))
        tablas = {"sistema_medicion_linealidad": pd.DataFrame([["Campo", "Valor"]], columns=["a", "b"])}
        copia = {k: v.copy() for k, v in tablas.items()}
        salida = rm._con_posicion_inicial(tablas, {"fecha": S1, "serie": SERIE_A})
        assert salida is tablas and list(salida) == list(copia) and salida["sistema_medicion_linealidad"].equals(copia["sistema_medicion_linealidad"])

    def test_sin_prueba_aplicable_no_suma_ninguna_tabla(self, rm, bd, monkeypatch):
        import pandas as pd
        _sembrar(bd)
        tablas = {"condiciones_medicion": pd.DataFrame([["Campo", "Valor"]], columns=["Condiciones de medición", ""])}
        assert list(rm._con_posicion_inicial(tablas, {"fecha": S1, "serie": SERIE_A})) == ["condiciones_medicion"]

    def test_el_orden_de_las_tablas_del_mensual_tiene_las_dos_claves_justo_despues_de_las_condiciones(self):
        """M11 / H5: las dos claves van JUSTO DESPUES de `condiciones_medicion` y no al final: el `Spacer` tras cada tabla depende de que no sea la ultima de `orden_tablas`."""
        import inspect
        import models.PDF.pdf as pdf_mod
        fuente = inspect.getsource(pdf_mod.generar_reporte_pdf_multitabla_mensual)
        orden = ast.literal_eval(re.search(r"orden_tablas = (\['tipo_calibracion'.*?\])", fuente, re.S).group(1))
        i = orden.index("condiciones_medicion")
        assert orden[i + 1:i + 3] == ["posicion_inicial", "grafico_posicion_inicial"], orden
        assert orden[-1] == "resultados_actividad", "las claves nuevas no van al final"

    def test_las_dos_claves_estan_en_las_listas_de_estilo_de_su_tipo(self):
        """La seccion es una tabla de dos columnas (como `condiciones_medicion`) y el grafico una de una columna con imagen (como `grafico_maximos`): en el ancho y en el estilo."""
        import inspect
        import models.PDF.pdf as pdf_mod
        fuente = inspect.getsource(pdf_mod.generar_reporte_pdf_multitabla_mensual)
        assert fuente.count("nombre_tabla in ['tipo_calibracion', 'sistema_medicion', 'condiciones_medicion', 'posicion_inicial',") == 2, "la seccion va en las dos listas de las tablas de 2 columnas (ancho y estilo)"
        assert fuente.count("'grafico_maximos', 'grafico_linealidad', 'grafico_posicion_inicial']") == 2, "el grafico va en las dos listas de las tablas de graficos (ancho y estilo)"
