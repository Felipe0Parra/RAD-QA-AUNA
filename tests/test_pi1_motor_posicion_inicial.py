"""PI.1 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md): el motor de la "Posición inicial" de braquiterapia
mide lo que mide el notebook corregido del físico -- y dice "no medible" cuando no se puede.

CAUSA. El análisis vivía solo en un notebook, con cuatro defectos medidos (§2.2 del plan): V1 línea
horizontal -> ZeroDivisionError; V2 mancha cortada por el borde de la película, dentro del área útil, medida
en silencio (hasta 36 px de error con estado "ok"); V3 la línea de marcador tapa un borde de la meseta y corre
el centro hasta 0.27 mm; V4 el signo depende de cómo quedó la imagen.

Nada aquí compara el motor consigo mismo: la exactitud se prueba con desfase CONOCIDO (placas pintadas con
supersampleo 8x, cuyo centro verdadero se sabe al subpíxel, y la placa sintética del físico), y lo que no se
puede medir se prueba con placas cortadas, con la línea sobre el borde y con una franja del escáner.

Criterios G1-G10 del plan (§2.3), uno o más tests cada uno:
  G1  placa real braqui_00 (recorte): número, sentido físico, capas RGB      G6  mancha cortada por el borde
  G2  la página completa del escáner (la placa incrustada en la hoja)        G7  rejilla de deslizadores
  G3  la página girada 180 grados: el signo de la imagen se invierte,        G8  modelo 1/r^2 del notebook
      el sentido físico no                                                    G9  banda de tránsito
  G4  línea exactamente horizontal (antes: ZeroDivisionError)                G10 sin resolución: no hay mm
  G5  geometría subpíxel exacta

La RESOLUCIÓN (obstáculo del 01-10, diagnosticado por Opus): Pillow rellena `info["dpi"]` con 72 en un JPEG con
EXIF sin resolución y con 1 en un TIFF sin la etiqueta; el motor lee solo lo que el archivo DECLARA
(`analisisImagenes/resolucion_imagen.py`) y solo convierte a milímetros a las resoluciones validadas (`escala_mm`,
hoy 600 dpi): una resolución ausente, o declarada pero no validada (una captura de pantalla de 96 dpi), da píxeles y
un aviso, nunca milímetros ni veredicto (DD6).

`TestIdentidadDelAlgoritmoPI1` reúne los NÚMEROS EXACTOS del motor corregido en el entorno de la app (Python 3.11,
OpenCV 4.11) y la huella de su versión y parámetros: cambian juntos con `VERSION_ALGORITMO` (DD3). Los demás tests
dicen la verdad física con las tolerancias del plan y no dependen de esos números.

Rojo real (protocolo de PI.1, punto 6), con el motor sustituido por
`PLAN_POSICION_INICIAL_BRAQUI_01-10_anexo/adaptador_notebook_sin_corregir.py` (el notebook sin corregir) y ESTE mismo
archivo, medido el 01-10: caen 31 de 86 y ninguna por `NameError`/`KeyError` del adaptador:
  V1  ZeroDivisionError ........ 2   G4 y el ángulo horizontal
  V2  cortes con estado "ok" ... 12  G6, por la izquierda y por la derecha (incluida la línea sobre el borde)
  V3  error > 0.05 mm .......... 4   G7, los cuatro pares de anchos
  V4  lado_transito None ....... 9   sentido físico de G1 y G2, G3, desnivel contrario de los clics, G9 con banda
                                     (3), sentidos opuestos y la franja del escáner
  subpíxel ..................... 1   G5, error máximo
  identidad PI-1 ............... 3   números de control de G1 y de la hoja, versión y parámetros
Además, cada corrección se desactiva POR SEPARADO sobre el motor corregido (V1: ángulo con arctan; V2: caída de
borde enorme; V3: contar cuerdas con borde tapado; V4: lado de tránsito nunca decidido; subpíxel: bordes enteros) y
cae exactamente el grupo de tests que la guarda. La lectura de la resolución se mutó igual (siete mutaciones).

Compuertas de no vacuidad (Trampa 8): cada rejilla declara cuántos casos corrió y cuántos mide de verdad
(un motor que dijera "no medible" a todo pasaría el máximo de error en vacío), y la franja del escáner afirma que el
detector LA VE antes de afirmar que la rechaza.
"""
import ast
import hashlib
import io
import struct
from datetime import date
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational, ImageFileDirectory_v2

from analisisImagenes import posicion_inicial_braqui as motor

ROOT = Path(__file__).resolve().parent.parent
DATOS = Path(__file__).resolve().parent / "datos"
MOTOR_PY = ROOT / "analisisImagenes" / "posicion_inicial_braqui.py"

PLACA_REAL = DATOS / "braqui_00.jpeg"
MD5_PLACA_REAL = "b9a924c0229ba369ee739bb71a3e6dd2"
CLICS_PLACA_REAL = [(191, 377), (190, 56)]          # los del físico sobre braqui_00.jpeg
MM_POR_PX = 25.4 / 600.0

# Valores de control del motor corregido, entorno de la app (Python 3.11.16, OpenCV 4.11.0, numpy 2.3.4);
# salen de PLAN_POSICION_INICIAL_BRAQUI_01-10_anexo/valores_control_3.11.16.json.
CONTROL_G1_PX = -8.553322
CONTROL_G1_MM = -0.362091
CONTROL_G1_U_MM = 0.0897
CONTROL_G1_TRANSITO = {"banda": 182.28125, "arriba": 167.53125, "abajo": 169.12744140625}


# ----------------------------------------------------------------------------------------- ayudas

def _bgr(gris):
    return cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)


def _escena(xs, xl, alto=467, ancho=1328, y_c=216.0, radio=70.0, h=45.0, borde=None, ss=8, franja=16):
    """Escaneo (mancha oscura, uint8) pintado con supersampleo 8x: los bordes de la línea y de la película
    salen con el área exacta, así que el centro verdadero de la mancha (xs) y la línea (xl) se saben al
    subpíxel. Es la escena de la batería G5/G6 del anexo, idéntica al bit, pintada por franjas de filas para
    no pedir 2.5 GB de memoria."""
    salida = np.empty((alto, ancho), np.uint8)
    cols = (np.arange(ancho * ss) + 0.5) / ss - 0.5
    X = cols[None, :]
    D_sat = h ** 2 / (radio ** 2 + h ** 2)
    en_linea = np.abs(X - xl) <= 4.5
    for y0 in range(0, alto, franja):
        y1 = min(alto, y0 + franja)
        Y = ((np.arange(y0 * ss, y1 * ss) + 0.5) / ss - 0.5)[:, None]
        D = h ** 2 / ((X - xs) ** 2 + (Y - y_c) ** 2 + h ** 2)
        s = np.clip(180 + 75 * (D / D_sat) ** 1.07, 0, 255)
        s[en_linea & (Y >= 20) & (Y <= alto - 20)] = 255
        if borde is not None:
            s[:, cols < borde] = 60
        s = s.reshape(y1 - y0, ss, ancho, ss).mean(axis=(1, 3))
        salida[y0:y1] = (255 - np.round(s)).astype(np.uint8)
    return salida


def _modelo_uno_sobre_r2(desfase_mm, linea_oscura):
    """El modelo 1/r^2 del notebook (G8): mancha que satura a 70 px, línea tan oscura como la meseta o más
    clara, ruido y JPEG. Devuelve el escaneo en gris; la mancha queda `desfase_mm` a la izquierda de la línea."""
    rng = np.random.default_rng(0)
    xs = 190.0 - desfase_mm / MM_POR_PX
    X, Y = np.meshgrid(np.arange(1328), np.arange(467))
    D = 45.0 ** 2 / ((X - xs) ** 2 + (Y - 216.0) ** 2 + 45.0 ** 2)
    s = 180 + 75 * (D / (45.0 ** 2 / (70 ** 2 + 45.0 ** 2))) ** 1.07 + rng.normal(0, 1.2, (467, 1328))
    s[:, :15] = 60
    s[20:450, 186:195] = 255 if linea_oscura else 225
    escaneo = (255 - np.clip(s, 0, 255)).astype(np.uint8)
    _, comprimida = cv2.imencode(".jpg", escaneo, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return cv2.imdecode(comprimida, cv2.IMREAD_GRAYSCALE)


def _con_transito(lado, x_mancha, amp=0.05):
    """Placa con banda de tránsito del lado `lado` ('derecha' | 'izquierda' | None) a lo largo del catéter;
    la línea cae 7 px a la izquierda del centro de la mancha. Devuelve (gris, color, x_de_la_línea)."""
    X, Y = np.meshgrid(np.arange(1328), np.arange(467))
    D = 45.0 ** 2 / ((X - x_mancha) ** 2 + (Y - 216.0) ** 2 + 45.0 ** 2)
    if lado:
        D = D + amp * ((X > x_mancha) if lado == "derecha" else (X < x_mancha)) * 45.0 ** 2 / ((Y - 216.0) ** 2 + 45.0 ** 2)
    s = 180 + 75 * (D / (45.0 ** 2 / (70 ** 2 + 45.0 ** 2))) ** 1.07 + np.random.default_rng(1).normal(0, 1.2, (467, 1328))
    xl = int(round(x_mancha - 7))
    s[20:450, xl - 4:xl + 5] = 255
    escaneo = (255 - np.clip(s, 0, 255)).astype(np.uint8)
    return escaneo, _bgr(escaneo), xl


def _con_franja_del_escaner():
    """Sin tránsito, pero con una franja horizontal del escáner a todo lo ancho, alineada con el catéter:
    no debe confundirse con la banda."""
    escaneo, _, xl = _con_transito(None, 664.0)
    invertida = 255.0 - escaneo.astype(float)
    invertida[195:240, :] += 8.0
    escaneo = (255 - np.clip(invertida, 0, 255)).astype(np.uint8)
    return escaneo, _bgr(escaneo), xl


def _analizar_gris(escaneo, clics, dpi=600.0):
    return motor.analizar(escaneo, _bgr(escaneo), dpi, clics)


# ----------------------------------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def bytes_placa_real():
    assert PLACA_REAL.exists(), "falta tests/datos/braqui_00.jpeg (la placa real de referencia)"
    return PLACA_REAL.read_bytes()


@pytest.fixture(scope="module")
def placa_real(bytes_placa_real):
    gris, color, dpi, fecha = motor.leer_imagen(bytes_placa_real)
    resultado = motor.analizar(gris, color, dpi, CLICS_PLACA_REAL)
    return {"gris": gris, "color": color, "dpi": dpi, "fecha": fecha,
            "resultado": resultado, "resumen": motor.resumen(resultado)}


# ----------------------------------------------------------------------------------------- lectura de la imagen

class TestLecturaDeLaImagen:
    def test_la_fixture_es_la_placa_de_referencia(self, bytes_placa_real):
        # Si alguien cambia la imagen, los valores de control dejan de significar nada: que lo diga aquí.
        assert hashlib.md5(bytes_placa_real).hexdigest() == MD5_PLACA_REAL
        assert len(bytes_placa_real) == 199455

    def test_decodifica_desde_bytes_y_trae_resolucion_y_fecha(self, placa_real):
        assert placa_real["gris"].shape == (467, 1328)
        assert placa_real["color"].shape == (467, 1328, 3)
        assert placa_real["dpi"] == 600.0
        assert placa_real["fecha"] == date(2026, 9, 30)      # EXIF DateTime que escribió el Epson

    def test_bytes_que_no_son_imagen_dicen_que_no_se_reconocen(self):
        with pytest.raises(ValueError, match="No se reconoce el formato"):
            motor.leer_imagen(b"esto no es una imagen")

    def test_la_fecha_prefiere_la_de_captura_a_datetime(self):
        """DateTimeOriginal > DateTimeDigitized > DateTime (que un editor puede reescribir)."""
        def jpeg(ifd0=None, exif=None):
            lienzo = Image.new("L", (64, 64), 128)
            datos = Image.Exif()
            for etiqueta, valor in (ifd0 or {}).items():
                datos[etiqueta] = valor
            interno = datos.get_ifd(0x8769)
            for etiqueta, valor in (exif or {}).items():
                interno[etiqueta] = valor
            salida = io.BytesIO()
            lienzo.save(salida, "JPEG", exif=datos)
            return salida.getvalue()

        solo_datetime = jpeg(ifd0={306: "2026:02:10 08:00:00"})
        assert motor.leer_imagen(solo_datetime)[3] == date(2026, 2, 10)
        con_captura = jpeg(ifd0={306: "2026:02:10 08:00:00"}, exif={36867: "2026:01:05 09:30:00"})
        assert motor.leer_imagen(con_captura)[3] == date(2026, 1, 5)
        con_digitalizada = jpeg(ifd0={306: "2026:02:10 08:00:00"}, exif={36868: "2026:01:07 09:30:00"})
        assert motor.leer_imagen(con_digitalizada)[3] == date(2026, 1, 7)

    def test_sin_fecha_o_con_fecha_ilegible_devuelve_none_sin_caerse(self):
        sin_exif = io.BytesIO()
        Image.new("L", (64, 64), 128).save(sin_exif, "JPEG")
        assert motor.leer_imagen(sin_exif.getvalue())[3] is None
        for basura in ("0000:00:00 00:00:00", "    :  :     ", "ayer", "2026:13:45 10:00:00"):
            lienzo = Image.new("L", (64, 64), 128)
            datos = Image.Exif()
            datos[306] = basura
            salida = io.BytesIO()
            lienzo.save(salida, "JPEG", exif=datos)
            assert motor.leer_imagen(salida.getvalue())[3] is None, basura


# ----------------------------------------------------------------------------------------- la resolución

# Obstáculo del 01-10 (diagnosticado por Opus): `Image.open(...).info["dpi"]` de Pillow RELLENA 72 dpi en un JPEG
# con EXIF sin resolución y 1 dpi en un TIFF sin la etiqueta; con eso el motor habría convertido a milímetros con
# una escala inventada (DD6: nunca se inventa la escala). Estos archivos reproducen cada forma real que se midió
# (los Epson del físico, una captura de pantalla de 96 dpi, el TIFF re-guardado por Windows) sin depender de
# `ImagenesDeReferencia/`, que está fuera del repo.

def _jpeg(dpi=None, exif=None):
    kw = {}
    if dpi is not None:
        kw["dpi"] = dpi
    if exif is not None:
        datos = Image.Exif()
        for etiqueta, valor in exif.items():
            datos[etiqueta] = valor
        kw["exif"] = datos
    salida = io.BytesIO()
    Image.new("L", (64, 64), 128).save(salida, "JPEG", **kw)
    return salida.getvalue()


def _parchear_jfif(datos, unidad, dx, dy):
    """Reescribe la unidad y la densidad del APP0 (JFIF) de un JPEG, para casos que Pillow no deja escribir."""
    d = bytearray(datos)
    assert d[6:11] == b"JFIF\x00", d[:20]
    d[13] = unidad
    d[14:16] = struct.pack(">H", dx)
    d[16:18] = struct.pack(">H", dy)
    return bytes(d)


def _tiff(dpi=None, etiquetas=None):
    kw = {}
    if dpi is not None:
        kw["dpi"] = dpi
    if etiquetas is not None:
        ifd = ImageFileDirectory_v2()
        for etiqueta, valor in etiquetas.items():
            ifd[etiqueta] = valor
        kw["tiffinfo"] = ifd
    salida = io.BytesIO()
    Image.new("L", (64, 64), 128).save(salida, "TIFF", **kw)
    return salida.getvalue()


def _png(dpi=None):
    salida = io.BytesIO()
    Image.new("L", (64, 64), 128).save(salida, "PNG", **({"dpi": dpi} if dpi else {}))
    return salida.getvalue()


def _bmp(ppm_cero=False):
    salida = io.BytesIO()
    Image.new("L", (64, 64), 128).save(salida, "BMP")
    d = bytearray(salida.getvalue())
    if ppm_cero:
        d[38:46] = b"\x00" * 8
    return bytes(d)


def _webp():
    salida = io.BytesIO()
    Image.new("RGB", (64, 64), (128, 128, 128)).save(salida, "WEBP")
    return salida.getvalue()


def _dpi(datos):
    return motor.leer_imagen(datos)[2]


# Lo que Pillow RELLENA (o el archivo escribe sin unidad física, o con una sola cifra imposible): no es resolución.
SIN_RESOLUCION = (
    ("JPEG sin EXIF ni dpi", lambda: _jpeg()),
    ("JPEG con EXIF (solo DateTime) y sin resolución: Pillow dice 72", lambda: _jpeg(exif={306: "2026:03:04 10:00:00"})),
    ("TIFF sin etiquetas de resolución: Pillow dice 1", lambda: _tiff()),
    ("PNG sin pHYs", lambda: _png()),
    ("JPEG con EXIF 600 pero unidad 1 ('sin unidad')", lambda: _jpeg(exif={282: 600.0, 283: 600.0, 296: 1})),
    ("TIFF con 600 pero unidad 1 ('sin unidad')", lambda: _tiff(etiquetas={282: 600.0, 283: 600.0, 296: 1})),
    ("JPEG con EXIF 0/0", lambda: _jpeg(exif={282: IFDRational(0, 0), 283: IFDRational(0, 0), 296: 2})),
    ("BMP con ppm 0", lambda: _bmp(ppm_cero=True)),
    ("WebP (sin lectura de resolución)", lambda: _webp()),
)

# Dos declaraciones que no coinciden, o píxel no cuadrado: no hay escala única.
CONTRADICTORIAS = (
    ("JFIF 96 dpi y EXIF 600 dpi a la vez", lambda: _jpeg(dpi=(96, 96), exif={282: 600.0, 283: 600.0, 296: 2})),
    ("TIFF con X 600 y Y 300 (píxel no cuadrado)", lambda: _tiff(etiquetas={282: 600.0, 283: 300.0, 296: 2})),
)

# Lo que el archivo ESCRIBE con unidad física, tal cual (también el 72 que es de verdad).
DECLARADAS = (
    ("PNG con 300 dpi", lambda: _png((300, 300)), 300.0, 0.01),
    ("JPEG con JFIF unidad 1 y 72 (un 72 REAL)", lambda: _jpeg(dpi=(72, 72)), 72.0, 0.01),
    ("JPEG con EXIF 72 escrito", lambda: _jpeg(exif={282: 72.0, 283: 72.0, 296: 2}), 72.0, 0.01),
    ("JPEG con JFIF unidad 0 y EXIF 600 (así sale el Epson: braqui_00 y EPSON031)", lambda: _jpeg(exif={282: 600.0, 283: 600.0, 296: 2}), 600.0, 0.01),
    ("JPEG con EXIF 600 sin ResolutionUnit (pulgada por defecto)", lambda: _jpeg(exif={282: 600.0, 283: 600.0}), 600.0, 0.01),
    ("JPEG con EXIF 236.22 por cm", lambda: _jpeg(exif={282: 236.22, 283: 236.22, 296: 3}), 600.0, 0.01),
    ("JPEG con JFIF unidad 2 (236 por cm)", lambda: _parchear_jfif(_jpeg(), 2, 236, 236), 599.44, 0.01),
    ("JPEG con JFIF unidad 1 de densidad 0 y EXIF 600", lambda: _parchear_jfif(_jpeg(exif={282: 600.0, 283: 600.0, 296: 2}), 1, 0, 0), 600.0, 0.01),
    ("JPEG con JFIF 599 (entero) y EXIF 599.999 (racional): la misma declaración", lambda: _jpeg(dpi=(599, 599), exif={282: 599.999, 283: 599.999, 296: 2}), 599.999, 1e-6),
    ("TIFF con 600 dpi", lambda: _tiff(dpi=(600, 600)), 600.0, 0.01),
    ("BMP de Pillow (96 por defecto)", lambda: _bmp(), 96.0, 0.01),
)


class TestResolucionDeclarada:
    def test_lo_que_pillow_rellena_no_es_resolucion(self):
        for nombre, fabrica in SIN_RESOLUCION:
            assert _dpi(fabrica()) is None, nombre

    def test_pillow_si_inventa_esos_valores(self):
        """El defecto que motiva todo esto, comprobado contra Pillow: si algún día Pillow deja de rellenar, este
        test lo dice y se puede revisar si la regla sigue haciendo falta."""
        relleno = {Image.open(io.BytesIO(f())).info.get("dpi") for n, f in SIN_RESOLUCION[1:3]}
        assert relleno == {(72, 72), (1, 1)}, relleno

    def test_dos_resoluciones_distintas_o_pixel_no_cuadrado_no_dan_escala(self):
        for nombre, fabrica in CONTRADICTORIAS:
            assert _dpi(fabrica()) is None, nombre

    def test_lo_declarado_se_lee_en_cada_forma(self):
        assert len(DECLARADAS) >= 10, "la lista cubre las formas reales que se midieron"
        for nombre, fabrica, esperado, tolerancia in DECLARADAS:
            leido = _dpi(fabrica())
            assert leido is not None, nombre
            assert leido == pytest.approx(esperado, rel=tolerancia), (nombre, leido)

    def test_el_epson_del_fisico_se_lee_a_600(self, placa_real):
        # braqui_00.jpeg: JFIF unidad 0 + EXIF 600/pulgada (la declaración real del Epson WF-6590)
        assert placa_real["dpi"] == 600.0
        assert Image.open(PLACA_REAL).info.get("jfif_unit") == 0

    def test_la_fecha_no_se_pierde_cuando_la_resolucion_falta(self):
        datos = _jpeg(exif={306: "2026:03:04 10:00:00"})            # EXIF sin resolución
        _, _, dpi, fecha = motor.leer_imagen(datos)
        assert dpi is None
        assert fecha == date(2026, 3, 4)


class TestEscalaEnMilimetros:
    """`escala_mm` es el ÚNICO lugar donde una resolución se vuelve escala: solo se convierte a milímetros a las
    resoluciones en que el método está validado (G1-G10 se corrieron a 600 dpi y sus parámetros están en píxeles)."""
    P = motor.PARAMETROS

    def test_las_resoluciones_del_epson_dan_escala(self):
        for dpi in (600.0, 599.999, 599.0, 601.0, 594.5):
            assert motor.escala_mm(dpi, self.P) == pytest.approx(25.4 / dpi), dpi

    @pytest.mark.parametrize("dpi", (300.0, 200.0, 150.0, 96.012, 96.0, 95.0, 72.0, 1.0, 1200.0, 590.0, 610.0))
    def test_una_resolucion_no_validada_no_da_escala(self, dpi):
        assert motor.escala_mm(dpi, self.P) is None

    @pytest.mark.parametrize("dpi", (None, 0, 0.0))
    def test_sin_resolucion_no_da_escala(self, dpi):
        assert motor.escala_mm(dpi, self.P) is None

    def test_la_regla_viaja_con_los_parametros_y_no_esta_fija_en_el_codigo(self):
        a_300 = dict(self.P, resoluciones_validadas_dpi=[300.0])
        assert motor.escala_mm(300.0, a_300) == pytest.approx(25.4 / 300.0)
        assert motor.escala_mm(600.0, a_300) is None
        ambas = dict(self.P, resoluciones_validadas_dpi=[300.0, 600.0])
        assert motor.escala_mm(300.0, ambas) is not None and motor.escala_mm(600.0, ambas) is not None
        estrecha = dict(self.P, tolerancia_dpi_relativa=1e-9)
        assert motor.escala_mm(599.999, estrecha) is None

    def test_analizar_guarda_la_regla_con_la_que_corrio(self, placa_real):
        r = motor.analizar(placa_real["gris"], placa_real["color"], 300.0, CLICS_PLACA_REAL,
                           parametros={"resoluciones_validadas_dpi": [300.0]})
        assert r["parametros"]["resoluciones_validadas_dpi"] == [300.0]
        assert r["tamano_pixel_mm"] == pytest.approx(25.4 / 300.0)
        s = motor.resumen(r)
        assert s["desfase_mm"] == pytest.approx(s["desfase_px"] * 25.4 / 300.0)

    @pytest.mark.parametrize("declarado", (300.0, 200.0, 96.012, 96.0, 72.0))
    def test_una_resolucion_declarada_y_no_validada_no_da_milimetros_ni_veredicto(self, placa_real, declarado):
        """El peligro que se midió: la MISMA placa de 600 dpi reales, declarada a 300, daba -0.72 mm 'Cumple'; a 200,
        -1.08 mm 'No cumple'; a 96 o 72, un 'no medible' con motivo falso."""
        r = motor.analizar(placa_real["gris"], placa_real["color"], declarado, CLICS_PLACA_REAL)
        s = motor.resumen(r)
        assert r["dpi"] == declarado                                   # se guarda lo que el archivo declaró
        assert r["tamano_pixel_mm"] is None
        assert s["estado"] == "ok"
        assert s["desfase_px"] == pytest.approx(placa_real["resumen"]["desfase_px"], abs=1e-9)
        assert s["desfase_mm"] is None
        assert s["veredicto"] == "No medible"
        assert f"declara {declarado:g} dpi" in s["aviso"]
        assert "validado a 600 dpi" in s["aviso"]
        assert "desfase_fisico_mm" not in s and "sentido" not in s

    def test_el_600_del_epson_es_valido(self, placa_real):
        """Lo que el Epson declara (600, o 599.999 en EXIF, o 599 en JFIF) da milímetros con SU escala."""
        for declarado in (600.0, 599.999, 599.0):
            r = motor.analizar(placa_real["gris"], placa_real["color"], declarado, CLICS_PLACA_REAL)
            s = motor.resumen(r)
            assert s["estado"] == "ok" and s["veredicto"] == "Cumple", declarado
            assert r["tamano_pixel_mm"] == pytest.approx(25.4 / declarado)
            assert s["desfase_mm"] == pytest.approx(s["desfase_px"] * 25.4 / declarado), declarado

    def test_una_captura_de_pantalla_de_la_placa_no_da_milimetros(self, placa_real):
        """De punta a punta, por la lectura del archivo: la placa real re-guardada como captura de pantalla (JFIF
        unidad 1, 96 dpi: lo que declara una captura de verdad) llega a 'sin milimetros ni veredicto'. Lo único que
        cambia entre las dos lecturas es la resolución declarada: los píxeles son idénticos, sin tolerancia."""
        salida = io.BytesIO()
        Image.open(PLACA_REAL).save(salida, "JPEG", dpi=(96, 96), quality=100)
        gris, color, dpi, _ = motor.leer_imagen(salida.getvalue())
        assert dpi == 96.0
        s = motor.resumen(motor.analizar(gris, color, dpi, CLICS_PLACA_REAL))
        con_600 = motor.resumen(motor.analizar(gris, color, 600.0, CLICS_PLACA_REAL))
        assert s["estado"] == "ok" and con_600["estado"] == "ok"
        assert s["desfase_px"] == con_600["desfase_px"]
        assert con_600["desfase_mm"] is not None                    # a 600 dpi declarados esa misma imagen SÍ mide
        assert s["desfase_mm"] is None and s["veredicto"] == "No medible"
        assert "declara 96 dpi" in s["aviso"]


# ----------------------------------------------------------------------------------------- G1: la placa real

class TestG1PlacaReal:
    def test_g1_la_medida_es_la_esperada(self, placa_real):
        s = placa_real["resumen"]
        assert s["estado"] == "ok"
        assert -0.40 < s["desfase_mm"] < -0.33
        assert s["veredicto"] == "Cumple"
        assert s["filas"] >= 30, "cuerdas centrales de sobra: no es una medida de unas pocas filas"

    def test_g1_el_sentido_fisico_sale_de_la_banda_de_transito(self, placa_real):
        r, s = placa_real["resultado"], placa_real["resumen"]
        assert r["lado_transito"] == "derecha"
        assert s["sentido"] == "antes de la marca"
        assert s["desfase_fisico_mm"] == pytest.approx(s["desfase_mm"])
        derecha = r["contrastes_transito"]["derecha"]
        assert derecha["banda"] == pytest.approx(CONTROL_G1_TRANSITO["banda"], abs=0.05)
        assert derecha["arriba"] == pytest.approx(CONTROL_G1_TRANSITO["arriba"], abs=0.05)
        assert derecha["abajo"] == pytest.approx(CONTROL_G1_TRANSITO["abajo"], abs=0.05)
        assert derecha["contraste"] >= 5.0
        assert r["contrastes_transito"]["izquierda"] is None        # ahí no hay película que comparar

    def test_g1_las_capas_g_y_b_coinciden_con_el_gris_y_la_roja_no_se_mide(self, placa_real):
        perfiles = placa_real["resultado"]["perfiles"]
        gris = perfiles["gris"]["desfase_px"]
        for capa in ("G", "B"):
            assert perfiles[capa]["estado"] == "ok", capa
            assert abs(perfiles[capa]["desfase_px"] - gris) * MM_POR_PX < 0.03, capa
        # la capa roja satura hasta el borde de la película: el motor lo dice, no inventa un número
        assert perfiles["R"]["estado"].startswith("no medible")
        assert "desfase_px" not in perfiles["R"]


# ----------------------------------------------------------------------------------------- G2-G4: la página completa

# braqui_00.jpeg es EPSON031.JPG (5100 x 6600 px, carta a 600 dpi) girada 90 grados y recortada (§2.5): en la
# página, la película es una tira vertical sobre la hoja blanca y la línea de referencia es HORIZONTAL (es lo que
# el físico sube de verdad). La hoja se reconstruye incrustando el recorte girado 90 grados en sentido HORARIO
# (cv2.ROTATE_90_CLOCKWISE) en una hoja blanca de 6600 filas x 5100 columnas, con la esquina en x=2422, y=3496
# (correlación 0.9999 con la página real, medida el 01-10; en sentido antihorario sale -0.54). El plan decía
# "a la izquierda": era un error de redacción, aclarado por Opus el 01-10 (rótulo invertido en el script del anexo).
# La hoja es de 6600 filas x 5100 columnas (alto x ancho): con la forma traspuesta la medida girada 180 grados
# cambia 0.034 px.
HOJA_ALTO, HOJA_ANCHO = 6600, 5100
ORIGEN_DEL_RECORTE = (2422, 3496)               # x, y de la esquina del recorte girado dentro de la hoja
CLICS_G2 = [(2511, 3687), (2832, 3686)]          # los clics del físico sobre la página real EPSON031.JPG

# Valores de control de la referencia del anexo sobre ESTA hoja incrustada (no los de la página real: la hoja
# no es EPSON031.JPG al bit), entorno de la app.
CONTROL_HOJA_PX = -8.553321
CONTROL_HOJA_MM = -0.362091


def _clics_en_la_hoja(clics_del_recorte, alto_del_recorte=467):
    """Un clic (x, y) del recorte cae en la hoja en (x0 + alto - 1 - y, y0 + x): giro de 90 grados horario."""
    x0, y0 = ORIGEN_DEL_RECORTE
    return [(x0 + alto_del_recorte - 1 - y, y0 + x) for x, y in clics_del_recorte]


def _hoja_incrustada(gris, color):
    girado_gris = cv2.rotate(gris, cv2.ROTATE_90_CLOCKWISE)
    girado_color = cv2.rotate(color, cv2.ROTATE_90_CLOCKWISE)
    x0, y0 = ORIGEN_DEL_RECORTE
    alto, ancho = girado_gris.shape
    hoja_gris = np.full((HOJA_ALTO, HOJA_ANCHO), 255, np.uint8)
    hoja_color = np.full((HOJA_ALTO, HOJA_ANCHO, 3), 255, np.uint8)
    hoja_gris[y0:y0 + alto, x0:x0 + ancho] = girado_gris
    hoja_color[y0:y0 + alto, x0:x0 + ancho] = girado_color
    return hoja_gris, hoja_color


@pytest.fixture(scope="module")
def hoja(placa_real):
    gris, color = _hoja_incrustada(placa_real["gris"], placa_real["color"])
    clics = _clics_en_la_hoja(CLICS_PLACA_REAL)
    resultado = motor.analizar(gris, color, placa_real["dpi"], clics)
    return {"gris": gris, "color": color, "clics": clics, "dpi": placa_real["dpi"],
            "resultado": resultado, "resumen": motor.resumen(resultado)}


class TestPaginaCompleta:
    """G2, G3 y G4: lo que el físico sube de verdad (la página del escáner, con la línea horizontal)."""

    def test_g2_la_hoja_reproduce_la_pagina_real(self, hoja, placa_real):
        # los clics del recorte llevados a la hoja SON los clics de G2 sobre la página real: delata una
        # incrustación al revés (con el giro antihorario la correlación con la página real es -0.54)
        assert hoja["clics"] == CLICS_G2
        assert hoja["gris"].shape == (HOJA_ALTO, HOJA_ANCHO)
        (x1, y1), (x2, y2) = hoja["clics"]
        (cx1, cy1), (cx2, cy2) = CLICS_PLACA_REAL
        assert hoja["gris"][y1, x1] == placa_real["gris"][cy1, cx1]
        assert hoja["gris"][y2, x2] == placa_real["gris"][cy2, cx2]
        assert y1 - y2 in (0, 1, -1), "en la página la línea de referencia es horizontal"

    def test_g2_mide_lo_mismo_que_el_recorte(self, hoja, placa_real):
        s, s_recorte = hoja["resumen"], placa_real["resumen"]
        assert s["estado"] == "ok"
        assert abs(s["desfase_mm"] - s_recorte["desfase_mm"]) < 0.03
        assert s["desfase_px"] < 0
        assert s["veredicto"] == s_recorte["veredicto"] == "Cumple"

    def test_g2_el_sentido_fisico_de_la_pagina_es_el_del_recorte(self, hoja, placa_real):
        s, s_recorte = hoja["resumen"], placa_real["resumen"]
        assert hoja["resultado"]["lado_transito"] == "derecha"
        assert s["sentido"] == s_recorte["sentido"] == "antes de la marca"
        assert abs(s["desfase_fisico_mm"] - s_recorte["desfase_fisico_mm"]) < 0.03

    def test_g3_girada_180_el_signo_de_la_imagen_se_invierte_y_el_sentido_fisico_no(self, hoja):
        gris, color = cv2.rotate(hoja["gris"], cv2.ROTATE_180), cv2.rotate(hoja["color"], cv2.ROTATE_180)
        clics = [(HOJA_ANCHO - 1 - x, HOJA_ALTO - 1 - y) for x, y in hoja["clics"]]
        r = motor.analizar(gris, color, hoja["dpi"], clics)
        s0, s = hoja["resumen"], motor.resumen(r)
        assert s["estado"] == "ok"
        assert r["lado_transito"] == "izquierda"                       # la banda quedó del otro lado de la imagen
        assert s["desfase_px"] > 0 > s0["desfase_px"]                  # el signo de la IMAGEN se invirtió
        assert s["desfase_mm"] == pytest.approx(-s0["desfase_mm"], abs=0.01)
        assert s["sentido"] == s0["sentido"] == "antes de la marca"    # el sentido FÍSICO no
        assert s["desfase_fisico_mm"] == pytest.approx(s0["desfase_fisico_mm"], abs=0.01)

    def test_g3b_el_desnivel_contrario_de_los_clics_invierte_la_imagen_pero_no_el_sentido_fisico(self, hoja):
        """V4 literal (§2.2): con la línea horizontal, un desnivel de 1 px entre los clics gira la imagen +89.8 o
        -89.8 grados (180 de diferencia) e invierte izquierda/derecha. El signo de la IMAGEN cambia; el sentido
        FÍSICO, que sale de la banda de tránsito, no."""
        (x1, y1), (x2, y2) = hoja["clics"]                                # y2 = y1 - 1
        s0 = hoja["resumen"]
        for clics in ([(x1, y2), (x2, y1)], [(x2, y1), (x1, y2)]):        # dy = +1, y en el orden inverso
            r = motor.analizar(hoja["gris"], hoja["color"], hoja["dpi"], clics)
            s = motor.resumen(r)
            assert r["angulo"] == pytest.approx(-hoja["resultado"]["angulo"], abs=0.01)
            assert s["desfase_px"] > 0 > s0["desfase_px"]
            assert r["lado_transito"] == "izquierda"
            assert s["sentido"] == s0["sentido"] == "antes de la marca"
            assert abs(s["desfase_fisico_mm"] - s0["desfase_fisico_mm"]) < 0.03

    def test_g4_clics_exactamente_horizontales_no_se_caen(self, hoja):
        """V1: la fórmula del notebook dividía entre dy = 0 (ZeroDivisionError); en la página real la línea
        es horizontal y solo se salvaba porque el desnivel de los clics era de 1 px."""
        (x1, y1), (x2, _) = hoja["clics"]
        r = motor.analizar(hoja["gris"], hoja["color"], hoja["dpi"], [(x1, y1), (x2, y1)])
        s = motor.resumen(r)
        assert s["estado"] == "ok"
        assert -0.40 < s["desfase_mm"] < -0.33
        assert r["lado_transito"] == "derecha"
        assert r["angulo"] == pytest.approx(90.0)


class TestAnguloCanonico:
    """V1 y V4: el ángulo de giro, definido también con la línea horizontal y sin depender del orden de los clics."""

    def test_vertical_no_gira_y_el_orden_de_los_clics_no_importa(self):
        assert motor.angulo_canonico((190, 56), (190, 377)) == pytest.approx(0.0)
        assert motor.angulo_canonico((190, 377), (190, 56)) == pytest.approx(0.0)

    def test_horizontal_esta_definido_y_no_depende_del_orden(self):
        assert motor.angulo_canonico((2511, 3687), (2832, 3687)) == pytest.approx(90.0)
        assert motor.angulo_canonico((2832, 3687), (2511, 3687)) == pytest.approx(90.0)

    def test_es_igual_a_la_formula_del_notebook_donde_esa_funciona(self):
        rng = np.random.default_rng(7)
        casos = 0
        for _ in range(300):
            (x0, y0), (x1, y1) = rng.integers(0, 2000, size=(2, 2))
            if y1 == y0:
                continue
            vieja = -np.degrees(np.arctan((x1 - x0) / (y1 - y0)))
            assert motor.angulo_canonico((x0, y0), (x1, y1)) == pytest.approx(vieja, abs=1e-9)
            casos += 1
        assert casos > 250, "la comparación corrió sobre casos de verdad"

    def test_el_resultado_queda_en_menos_90_a_90(self):
        rng = np.random.default_rng(11)
        for _ in range(300):
            p0, p1 = rng.integers(0, 2000, size=(2, 2))
            if tuple(p0) == tuple(p1):
                continue
            assert -90.0 < motor.angulo_canonico(tuple(p0), tuple(p1)) <= 90.0


# ----------------------------------------------------------------------------------------- G5: geometría subpíxel

@pytest.fixture(scope="module")
def errores_g5():
    """32 placas: la mancha en 8 posiciones subpíxel y la línea en 4, con el desfase verdadero conocido."""
    errores = []
    for fraccion_mancha in np.arange(0, 1, 0.125):
        for fraccion_linea in (0.0, 0.25, 0.5, 0.75):
            xs, xl = 205.0 + fraccion_mancha, 190.0 + fraccion_linea
            escaneo = _escena(xs, xl)
            r = _analizar_gris(escaneo, [(int(round(xl)), 56), (int(round(xl)), 377)])
            perfil = r["perfiles"]["gris"]
            assert perfil["estado"] == "ok", (xs, xl, perfil["estado"])
            errores.append(perfil["desfase_px"] - (xl - xs))
    return np.array(errores)


class TestG5GeometriaSubpixel:
    def test_g5_corrio_los_32_casos(self, errores_g5):
        assert len(errores_g5) == 32

    def test_g5_sin_sesgo(self, errores_g5):
        assert abs(float(np.mean(errores_g5))) < 0.02

    def test_g5_error_maximo_de_una_decima_de_pixel(self, errores_g5):
        # el método sin bordes subpíxel llega a 0.34 px (cuantización de los bordes enteros)
        assert float(np.max(np.abs(errores_g5))) <= 0.10


# ----------------------------------------------------------------------------------------- G6: mancha cortada

CORTADA = "no medible: la mancha esta cortada por el borde de la pelicula"
LINEA_TAPA = "no medible: la linea tapa el borde de la meseta"


class TestG6ManchaCortadaPorElBordeDeLaPelicula:
    """V2: el borde de la película dentro del área útil (fuera del marco de 25 px) cortaba la mancha y el
    método sin corregir medía el centro de lo que quedaba, en silencio y con estado "ok" (hasta 36 px). Se afirma
    el estado EXACTO: con el criterio de caída brusca apagado, los cortes pasarían a "ok" y estos tests caerían.
    Con el borde en 80 la línea de marcador (columnas 113-127) tapa justo el borde de la meseta: allí el motor dice
    otra verdad, "la línea tapa el borde" (V3), y por eso ese caso no prueba V2 y se afirma aparte."""

    @pytest.mark.parametrize("borde,estado", ((30.0, CORTADA), (40.0, CORTADA), (60.0, CORTADA), (80.0, LINEA_TAPA),
                                              (100.0, CORTADA), (130.0, CORTADA)))
    def test_g6_cortada_por_la_izquierda_no_se_mide(self, borde, estado):
        escaneo = _escena(97.0 + 30, 90.0 + 30, borde=borde + 30)    # +30: lejos del marco del escaneo
        perfil = _analizar_gris(escaneo, [(120, 56), (120, 377)])["perfiles"]["gris"]
        assert perfil["estado"] == estado, borde
        assert "desfase_px" not in perfil

    @pytest.mark.parametrize("borde", (30.0, 40.0, 60.0, 130.0))
    def test_g6_cortada_por_la_derecha_no_se_mide(self, borde):
        """La misma placa espejada: el borde queda a la derecha de la mancha (la otra rama del criterio de caída;
        el método sin corregir medía 'ok' con hasta 51 px de error)."""
        escaneo = _escena(97.0 + 30, 90.0 + 30, borde=borde + 30)[:, ::-1].copy()
        perfil = _analizar_gris(escaneo, [(1207, 56), (1207, 377)])["perfiles"]["gris"]
        assert perfil["estado"] == CORTADA, borde
        assert "desfase_px" not in perfil

    @pytest.mark.parametrize("borde", (80.0, 100.0))
    def test_g6_espejada_con_la_linea_sobre_el_borde_tampoco_se_mide(self, borde):
        escaneo = _escena(97.0 + 30, 90.0 + 30, borde=borde + 30)[:, ::-1].copy()
        perfil = _analizar_gris(escaneo, [(1207, 56), (1207, 377)])["perfiles"]["gris"]
        assert perfil["estado"] == LINEA_TAPA, borde
        assert "desfase_px" not in perfil

    def test_g6b_entera_junto_a_un_borde_lejano_se_mide_y_exacta(self):
        # el mismo montaje con la película terminando lejos de la mancha: no hay corte, hay medida
        escaneo = _escena(97.0 + 30, 90.0 + 30, borde=10.0)
        perfil = _analizar_gris(escaneo, [(120, 56), (120, 377)])["perfiles"]["gris"]
        assert perfil["estado"] == "ok"
        assert perfil["desfase_px"] == pytest.approx(-7.0, abs=0.15)

    def test_g6b_espejada_entera_junto_a_un_borde_lejano_se_mide_y_exacta(self):
        escaneo = _escena(97.0 + 30, 90.0 + 30, borde=10.0)[:, ::-1].copy()
        perfil = _analizar_gris(escaneo, [(1207, 56), (1207, 377)])["perfiles"]["gris"]
        assert perfil["estado"] == "ok"
        assert perfil["desfase_px"] == pytest.approx(7.0, abs=0.15)      # espejada: la mancha queda al otro lado


# ----------------------------------------------------------------------------------------- G7: deslizadores

# Pisos de "casos que se miden" por par de anchos: lo medido el 01-10 (35 casos por par; 4, 3, 2 y 9 no
# medibles) menos 2 de margen. "No medible" es una respuesta honesta cuando la línea tapa un borde de la
# meseta en todas las cuerdas o la mancha toca el borde; un motor que lo dijera de más pasaría el error
# máximo en vacío.
PISOS_G7 = {(2.2, 1.1): 29, (3.0, 3.0): 30, (1.5, 1.5): 31, (5.0, 2.0): 24}


class TestG7RejillaDeDeslizadores:
    """Los deslizadores de la pestaña sintética (ancho X, ancho Y, saturación, desfase): la rejilla
    completa de la página, con la línea cayendo sobre el borde de la meseta en algunos desfases (V3)."""

    @pytest.mark.parametrize("ancho_x,ancho_y", sorted(PISOS_G7))
    def test_g7_error_en_lo_medible(self, ancho_x, ancho_y):
        peor, casos, medibles = 0.0, 0, 0
        for saturacion in (0.3, 0.5, 0.8, 0.95, 1.0):
            for desfase in (-3, -2, -1, 0, 1, 2, 3):
                gris, color, dpi, clics = motor.placa_sintetica(desfase, ancho_x, ancho_y, saturacion)
                s = motor.resumen(motor.analizar(gris, color, dpi, clics))
                casos += 1
                if s["estado"] == "ok":
                    medibles += 1
                    peor = max(peor, abs(s["desfase_mm"] - desfase))
        assert casos == 35
        assert medibles >= PISOS_G7[(ancho_x, ancho_y)], f"solo {medibles} de {casos} se miden"
        assert peor <= 0.05, f"peor error {peor:.4f} mm"


# ----------------------------------------------------------------------------------------- G8: modelo 1/r^2

class TestG8ModeloUnoSobreR2:
    """El modelo físico del notebook (mancha 1/r^2 que satura), desfases de 0 a -10 mm y +2, línea oscura
    y clara, sin tránsito: el error tiene que quedar en 0.02 mm."""

    @pytest.mark.parametrize("linea_oscura", (True, False))
    def test_g8_error_maximo(self, linea_oscura):
        peor, casos = 0.0, 0
        for desfase in (0.0, 0.25, -0.25, 0.5, -0.5, 1.0, -1.0, -2.0, -3.5, -5.0, -10.0, 2.0):
            escaneo = _modelo_uno_sobre_r2(desfase, linea_oscura)
            s = motor.resumen(_analizar_gris(escaneo, [(192, 56), (189, 377)]))
            assert s["estado"] == "ok", (desfase, linea_oscura, s)
            peor = max(peor, abs(s["desfase_mm"] - desfase))
            casos += 1
        assert casos == 12
        assert peor <= 0.02, f"peor error {peor:.4f} mm"


# ----------------------------------------------------------------------------------------- G9: tránsito

CASOS_G9 = (
    ("derecha, mancha a la izquierda", "derecha", 197.0),
    ("izquierda, mancha a la derecha", "izquierda", 1130.0),
    ("derecha, mancha al centro", "derecha", 664.0),
    ("sin banda, mancha al centro", None, 664.0),
    ("sin banda, mancha a la izquierda", None, 197.0),
)


class TestG9BandaDeTransito:
    @pytest.mark.parametrize("nombre,lado,x_mancha", CASOS_G9, ids=[c[0] for c in CASOS_G9])
    def test_g9_el_lado_correcto_y_no_inventa_banda(self, nombre, lado, x_mancha):
        escaneo, color, xl = _con_transito(lado, x_mancha)
        r = motor.analizar(escaneo, color, 600.0, [(xl, 56), (xl, 377)])
        assert r["perfiles"]["gris"]["estado"] == "ok"
        assert r["lado_transito"] == lado, (nombre, r["contrastes_transito"])

    def test_g9_una_franja_del_escaner_a_lo_ancho_no_se_confunde_con_la_banda(self):
        escaneo, color, xl = _con_franja_del_escaner()
        r = motor.analizar(escaneo, color, 600.0, [(xl, 56), (xl, 377)])
        assert r["perfiles"]["gris"]["estado"] == "ok"
        # el detector VE la franja (de lo contrario el test pasaría en vacío con un diccionario vacío) ...
        for lado in ("izquierda", "derecha"):
            d = r["contrastes_transito"].get(lado)
            assert d is not None and d["contraste"] >= motor.PARAMETROS["contraste_transito"], (lado, d)
        # ... y la rechaza, porque sobresale por los DOS lados
        assert r["lado_transito"] is None, r["contrastes_transito"]

    def test_g9_la_mancha_a_la_derecha_de_la_linea_en_la_imagen_da_sentidos_fisicos_opuestos(self):
        """V4 / D4: en las dos placas la mancha queda a la DERECHA de la línea en la imagen (desfase de la imagen
        negativo), pero el tránsito entra por lados opuestos: el sentido físico (antes / después de la marca) es el
        contrario. (El desfase de la imagen no coincide entre las dos: la banda ensancha la meseta hacia su lado y
        corre el centro a un lado u otro, ±4.4 px con esta banda de prueba -- el sesgo por tránsito del §6.4-1 del
        plan; lo que se afirma aquí es el signo físico, que es lo que la imagen no sabe.)"""
        r_der = motor.analizar(*_con_transito("derecha", 664.0)[:2], 600.0, [(657, 56), (657, 377)])
        r_izq = motor.analizar(*_con_transito("izquierda", 664.0)[:2], 600.0, [(657, 56), (657, 377)])
        s_der, s_izq = motor.resumen(r_der), motor.resumen(r_izq)
        assert s_der["estado"] == s_izq["estado"] == "ok"
        assert s_der["desfase_px"] < 0 and s_izq["desfase_px"] < 0
        assert r_der["lado_transito"] == "derecha" and r_izq["lado_transito"] == "izquierda"
        assert s_der["sentido"] == "antes de la marca" and s_der["desfase_fisico_mm"] < 0
        assert s_izq["sentido"] == "despues de la marca" and s_izq["desfase_fisico_mm"] > 0
        assert s_der["desfase_fisico_mm"] == pytest.approx(s_der["desfase_mm"])         # tránsito a la derecha: signo de la imagen
        assert s_izq["desfase_fisico_mm"] == pytest.approx(-s_izq["desfase_mm"])        # tránsito a la izquierda: signo contrario

    def test_g9_sin_banda_se_dice_en_la_imagen_y_no_en_el_mundo(self):
        escaneo, color, xl = _con_transito(None, 664.0)
        s = motor.resumen(motor.analizar(escaneo, color, 600.0, [(xl, 56), (xl, 377)]))
        assert s["desfase_fisico_mm"] is None
        assert "no se distingue la banda de transito" in s["sentido"]
        assert "antes de la marca" not in s["sentido"] and "despues de la marca" not in s["sentido"]


# ----------------------------------------------------------------------------------------- G10: sin resolución

class TestG10SinResolucion:
    def test_g10_hay_pixeles_pero_no_milimetros_ni_veredicto(self, placa_real):
        r = motor.analizar(placa_real["gris"], placa_real["color"], None, CLICS_PLACA_REAL)
        s = motor.resumen(r)
        assert r["tamano_pixel_mm"] is None
        assert s["estado"] == "ok"
        # la medida en píxeles no depende de los dpi: es la misma que con ellos (y la ventana usa 600 solo para su tamaño)
        assert s["desfase_px"] == pytest.approx(placa_real["resumen"]["desfase_px"], abs=1e-9)
        assert s["desfase_mm"] is None
        assert s["veredicto"] == "No medible"
        assert "no trae resolucion" in s["aviso"]


# ----------------------------------------------------------------------------------------- barrido sintético

class TestBarridoSintetico:
    def test_el_barrido_por_defecto_pasa_por_la_diagonal(self):
        """La gráfica real contra medido de la pestaña sintética (PI.5): 11 desfases de -5 a 5 mm con los
        valores por defecto del físico (2.2 / 1.1 mm, saturación 50 %)."""
        puntos = motor.barrido_sintetico(2.2, 1.1, 0.5)
        assert [real for real, _ in puntos] == [float(d) for d in range(-5, 6)]
        medidos = [(real, medido) for real, medido in puntos if medido is not None]
        assert len(medidos) >= 10, "el barrido por defecto mide casi todos los desfases"
        assert max(abs(medido - real) for real, medido in medidos) <= 0.05


# ----------------------------------------------------------------------------------------- pureza y versión

def _modulos_importados(ruta):
    """Primer componente de cada import del archivo, por AST (cubre `import x`, `import x.y`, `from x import y`)."""
    arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"))
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.update(a.name.split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.add(nodo.module.split(".")[0])
    return nombres


class TestPurezaDelMotor:
    """Sin Qt y sin base de datos: la página, el recálculo de lo guardado, la pestaña sintética y los tests usan
    el MISMO `analizar` (principio 1 del plan), y un motor que abriera la BD o una ventana no podría correr en los
    tests, ni en el recálculo de un registro, sin arrastrar la app."""
    PROHIBIDOS = {"PyQt5", "sqlite3", "data", "services"}

    def test_el_motor_no_importa_qt_ni_base_de_datos(self):
        importados = _modulos_importados(MOTOR_PY)
        assert {"cv2", "numpy"} <= importados, "el AST encontró los imports de verdad del motor"
        assert not importados & self.PROHIBIDOS, importados & self.PROHIBIDOS

    def test_el_detector_ve_a_un_intruso(self, tmp_path):
        intruso = tmp_path / "intruso.py"
        intruso.write_text("import numpy\nfrom PyQt5.QtWidgets import QWidget\nimport sqlite3\n"
                           "from data.ManejoDatos.conection import Conexion\nfrom services.anulacion import anular\n",
                           encoding="utf-8")
        assert _modulos_importados(intruso) >= self.PROHIBIDOS


# ----------------------------------------------------------------------------------------- identidad del algoritmo

class TestIdentidadDelAlgoritmoPI1:
    """Los números EXACTOS del motor corregido en el entorno de la app (Python 3.11, OpenCV 4.11) y la huella de
    su versión y sus parámetros. Cambian JUNTOS: si un número o un parámetro cambia hay que subir
    `VERSION_ALGORITMO` (DD3: al abrir un registro guardado se compara lo recalculado contra lo firmado), rehacer
    estos valores de control y anotar por qué. Caen con cualquier otro algoritmo, por diseño: son identidad, no
    criterio físico (los criterios son los G1-G10 de las demás clases, con las tolerancias del plan)."""

    def test_g1_valores_de_control_del_motor_corregido(self, placa_real):
        s = placa_real["resumen"]
        assert s["desfase_px"] == pytest.approx(CONTROL_G1_PX, abs=0.002)
        assert s["desfase_mm"] == pytest.approx(CONTROL_G1_MM, abs=0.0001)
        assert s["U_mm"] == pytest.approx(CONTROL_G1_U_MM, abs=0.001)

    def test_g2_valores_de_control_de_la_hoja(self, hoja):
        s = hoja["resumen"]
        assert s["desfase_px"] == pytest.approx(CONTROL_HOJA_PX, abs=0.002)
        assert s["desfase_mm"] == pytest.approx(CONTROL_HOJA_MM, abs=0.0001)

    def test_la_version_y_los_parametros_estan_fijados(self):
        """Cambiar un parámetro cambia los números: obliga a subir la versión y a rehacer los valores de control."""
        assert motor.VERSION_ALGORITMO == "PI-1"
        assert motor.PARAMETROS == {
            "grosor_marco": 25, "delta": 2.5, "ancho_linea": 7, "hueco_max": 10, "filtro": 5,
            "fraccion_central": 0.8, "fraccion_minima": 0.3, "minimo_filas": 10, "delta_cruces": 6,
            "caida_borde": 40, "fraccion_filas_cortadas": 0.2, "ventana_mm": 20.0, "margen_filas_mm": 3.0,
            "refinar_linea": True, "contraste_transito": 5.0, "transito_desde_mm": 12.0,
            "transito_hasta_mm": 50.0, "umbral_pelicula": 60.0, "tolerancia_mm": 1.0,
            # la escala en milímetros solo a las resoluciones validadas (obstáculo de la resolución, 01-10)
            "resoluciones_validadas_dpi": [600.0], "tolerancia_dpi_relativa": 0.01,
        }
        assert motor.DPI_SI_FALTA == 600.0
