"""PF.0 (PLAN_ANALISIS_PELICULAS_08-10.md): el corpus de peliculas reales y las placas sinteticas con verdad conocida.

CAUSA. Ninguna prueba de la suite cargaba una pelicula mensual real ni una sintetica con verdad conocida: la exactitud de los dos analisis
(el mensual de aceleradores y la posicion inicial de braqui) nunca se habia medido, solo su repetibilidad. Todas las tareas siguientes se verifican
contra la verdad; sin este andamiaje cada una inventaria el suyo.

QUE FIJA ESTE ARCHIVO.
  1. El CORPUS (`tests/_corpus.py`): las peliculas reales de `ImagenesDeReferencia/PlacasHistoricas`, con su propia raiz y la regla de PR.0 aplicada a esa
     raiz (si la carpeta existe y falta una pelicula declarada, FALLA nombrandola; si no existe, salta).
  2. El generador MENSUAL (`tests/_placa_mensual_sintetica.py`): el calibrado del anexo con DOS extensiones declaradas (un FWHM que varia linealmente con
     la posicion y una meseta en cupula). Determinista; JPEG q=95, PNG, TIFF de 8 y de 16 bits con o sin alfa; y su VERDAD: la de la dosis (FWHM, bordes,
     centros, giro, marcas) y, por capa, los bordes que predice la respuesta del propio generador (solo el azul es lineal en la dosis).
     La verdad cuadra con la imagen: el FWHM de la dosis generada sin ruido, medido con una integracion INDEPENDIENTE (interpolacion lineal del cruce del
     50 % sobre el arreglo, sin las funciones del modelo), coincide a +-0.01 mm; tambien con las dos extensiones, con la pelicula girada y por capa
     (sobre un TIFF de 16 bits sin ruido, donde la respuesta de cada capa se invierte sin perder precision).
  3. El generador de BRAQUI (`tests/_placa_braqui_sintetica.py`): el independiente y el fisico calibrado contra la mancha real, con las variantes
     dificiles de B.2. La verdad es el desfase conocido de la fuente; el punto medio de la mancha sin ruido, medido aqui, coincide con ella (y el modelo
     fisico, con su sesgo de unas decimas de mm por la anisotropia y el transito, que tambien se fija). Con la pagina rotada la verdad es la de la IMAGEN DEVUELTA, en el marco
     del motor (el desfase y el lado de la banda cambian de signo con k = 1 y 2): se mide en los pixeles de la pagina, sin pasar por el generador ni por el motor.
  4. La INDEPENDENCIA: ninguno de los dos generadores importa nada de la aplicacion (paso 13 del protocolo: no se valida un motor con su propio generador).

El rojo (protocolo de la tarea): sin los modulos, esto no importa; ademas, las mutaciones de `pf0_mutaciones.py` (anexo) rompen una pieza del generador o de
la regla del corpus y la prueba que la guarda cae por su razon.
"""
import ast
import hashlib
import io
import math
import os
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, JpegImagePlugin
from scipy.ndimage import map_coordinates

import _corpus
import _catphan_oro
import _placa_braqui_sintetica as GB
import _placa_mensual_sintetica as GM
from test_pr0_corpus_completo import peliculas_que_faltan, texto_del_fallo_de_peliculas, verificar_peliculas

TESTS = Path(__file__).resolve().parent
DATOS = TESTS / "datos"
DPI_PRUEBA = 100            # los formatos y la determinacion no necesitan los 600 dpi reales
DPI_MEDIDA = 150            # la verdad contra la imagen: el cruce al 50 % interpolado a 150 dpi coincide con la verdad a ~0.0005 mm


def _hay_peliculas():
    return os.path.isdir(_corpus.PELICULAS_RAIZ)


def _md5(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ============================================================================================================================
# 1. EL CORPUS DE PELICULAS
# ============================================================================================================================
# Las DIEZ peliculas mensuales que nombra PF.0 OBJETIVO 1 (ML0, EPSON027, EPSON007, EPSON008.TIF, EPSON030, EPSON001.jpg y .TIF, placa_ref40, EPSON028, EPSON029).
MENSUALES_DEL_PLAN = {
    "ML0": "ML0.JPG", "EPSON027": "EPSON027.JPG", "EPSON007": "EPSON007.JPG", "EPSON008_TIF": "EPSON008.TIF", "EPSON030": "EPSON030.JPG",
    "EPSON001_JPG": "EPSON001.jpg", "EPSON001_TIF": "EPSON001.TIF", "PLACA_REF40": "placa_ref40.jpeg", "EPSON028": "EPSON028.JPG",
    "EPSON029": "EPSON029.JPG",
}
# La UNICA que el registro declara de mas: la placa que se subio en el control mensual ref=6, que es EXACTAMENTE EPSON001.jpg (mismo md5; ver
# `_corpus.MISMO_ARCHIVO` y obstaculos.md #1). No es del plan: es un alias de una que si lo es.
MENSUALES_FUERA_DEL_PLAN = {"PLACA_REF6": "placa_ref6.jpeg"}
BRAQUI_DE_LOS_TESTS_PI = {
    "BRAQUI_00_JPEG": "braqui_00.jpeg", "BRAQUI_00_JPG": "braqui_00.JPG", "EPSON009": "EPSON009.jpeg", "EPSON031": "EPSON031.JPG",
}


class TestElCorpusDePeliculas:
    def test_las_peliculas_mensuales_declaradas_son_las_del_plan_mas_el_alias_PLACA_REF6(self):
        """El plan lista DIEZ peliculas mensuales; el registro declara esas diez y UNA mas, PLACA_REF6, que no es del plan: es la misma pelicula que EPSON001.jpg
        (la placa del control mensual ref=6). Lo que sobra respecto del plan tiene que ser eso, un alias de una del plan, y la prueba lo dice."""
        assert len(MENSUALES_DEL_PLAN) == 10
        assert {k: v for k, v in _corpus.PELICULAS_MENSUALES.items() if k in MENSUALES_DEL_PLAN} == MENSUALES_DEL_PLAN
        de_mas = {k: v for k, v in _corpus.PELICULAS_MENSUALES.items() if k not in MENSUALES_DEL_PLAN}
        assert de_mas == MENSUALES_FUERA_DEL_PLAN
        assert set(de_mas) == set(_corpus.MISMO_ARCHIVO), "lo declarado de mas es un alias (MISMO_ARCHIVO) de una pelicula del plan"
        assert set(_corpus.MISMO_ARCHIVO.values()) <= set(MENSUALES_DEL_PLAN)
        assert _corpus.PELICULAS_MENSUALES == {**MENSUALES_DEL_PLAN, **MENSUALES_FUERA_DEL_PLAN}

    def test_las_peliculas_de_braqui_declaradas_son_las_que_usan_los_tests_de_PI(self):
        assert _corpus.PELICULAS_BRAQUI == BRAQUI_DE_LOS_TESTS_PI
        for clave, nombre in _corpus.COPIAS_EN_EL_REPO.items():
            assert (DATOS / nombre).is_file(), f"{clave}: la copia {nombre} no esta en tests/datos/"

    def test_la_raiz_de_las_peliculas_es_PlacasHistoricas_y_no_se_confunde_con_las_otras_dos(self):
        raiz = os.path.normpath(_corpus.PELICULAS_RAIZ)
        assert raiz.endswith(os.path.join("ImagenesDeReferencia", "PlacasHistoricas"))
        assert raiz not in (os.path.normpath(_corpus.RAIZ), os.path.normpath(_corpus.CATPHAN_RAIZ))
        assert not raiz.startswith(os.path.normpath(_corpus.RAIZ) + os.sep)
        assert not raiz.startswith(os.path.normpath(_corpus.CATPHAN_RAIZ) + os.sep)

    def test_las_claves_de_mensuales_y_de_braqui_no_se_pisan(self):
        assert not set(_corpus.PELICULAS_MENSUALES) & set(_corpus.PELICULAS_BRAQUI)
        assert len(_corpus.todas_las_peliculas_declaradas()) == len(_corpus.PELICULAS_MENSUALES) + len(_corpus.PELICULAS_BRAQUI)
        assert set(_corpus.FORMA_DE_LAS_PELICULAS) == set(_corpus.todas_las_peliculas_declaradas())

    def test_el_corpus_declarado_existe(self):
        """La regla de PR.0 aplicada a la raiz de las peliculas: si la carpeta existe, estan TODAS las declaradas (si no existe, salta)."""
        verificar_peliculas(_corpus.PELICULAS_RAIZ, _corpus.todas_las_peliculas_declaradas())

    def test_con_una_ruta_rota_la_prueba_FALLA_nombrando_la_pelicula(self, tmp_path):
        """La carpeta existe y esta toda menos una pelicula (la ruta del registro apunta a un archivo que no esta): FALLA y dice cual."""
        declaradas = _corpus.todas_las_peliculas_declaradas()
        for relativa in declaradas.values():
            (tmp_path / relativa).write_bytes(b"x" * 16)
        verificar_peliculas(str(tmp_path), declaradas)                                    # completa: ni salta ni falla
        (tmp_path / declaradas["EPSON029"]).unlink()
        texto = texto_del_fallo_de_peliculas(str(tmp_path), declaradas)
        assert "EPSON029 ->" in texto and str(tmp_path / "EPSON029.JPG") in texto
        assert texto.count(" -> ") == 1, "solo debe nombrar la que falta"

    def test_con_el_registro_real_y_una_ruta_rota_FALLA_nombrando_la_pelicula(self, monkeypatch):
        if not _hay_peliculas():
            pytest.skip("no hay carpeta de peliculas reales en esta maquina (HI-0)")
        monkeypatch.setitem(_corpus.PELICULAS_MENSUALES, "ML0", "ML0_renombrada.JPG")
        texto = texto_del_fallo_de_peliculas(_corpus.PELICULAS_RAIZ, _corpus.todas_las_peliculas_declaradas())
        assert "ML0 ->" in texto and "ML0_renombrada.JPG" in texto

    def test_una_pelicula_que_falta_se_nombra_aunque_las_demas_esten(self, tmp_path):
        declaradas = _corpus.todas_las_peliculas_declaradas()
        for relativa in declaradas.values():
            (tmp_path / relativa).write_bytes(b"x" * 16)
        (tmp_path / declaradas["BRAQUI_00_JPG"]).unlink()
        (tmp_path / declaradas["EPSON007"]).unlink()
        assert peliculas_que_faltan(str(tmp_path), declaradas) == ["BRAQUI_00_JPG", "EPSON007"]

    @pytest.mark.parametrize("clave", sorted(_corpus.FORMA_DE_LAS_PELICULAS))
    def test_cada_pelicula_declarada_se_abre_y_tiene_la_forma_declarada(self, clave):
        ruta = _corpus.pelicula(clave)
        if ruta is None:
            if _hay_peliculas():
                pytest.fail(f"{clave}: la carpeta de peliculas existe y la pelicula no esta ({_corpus.todas_las_peliculas_declaradas()[clave]})")
            pytest.skip("no hay carpeta de peliculas reales en esta maquina (HI-0)")
        ancho, alto, formato = _corpus.FORMA_DE_LAS_PELICULAS[clave]
        with Image.open(ruta) as im:
            assert (im.size, im.format) == ((ancho, alto), formato), f"{clave}: {ruta}"

    def test_placa_ref6_es_el_mismo_archivo_que_EPSON001(self):
        if not _hay_peliculas():
            pytest.skip("no hay carpeta de peliculas reales en esta maquina (HI-0)")
        assert _corpus.MISMO_ARCHIVO == {"PLACA_REF6": "EPSON001_JPG"}
        for copia, original in _corpus.MISMO_ARCHIVO.items():
            assert _md5(_corpus.pelicula(copia)) == _md5(_corpus.pelicula(original)), f"{copia} ya no es {original}"

    def test_las_relaciones_entre_las_peliculas_del_corpus_son_las_que_dice_el_registro(self):
        """EPSON027 es la PAGINA de la que sale ML0 (recorte en el desplazamiento (8, 8)); EPSON031 es la pagina de la que salen braqui_00.JPG (recorte exacto)
        y braqui_00.jpeg (el mismo recorte retocado), con la pelicula girada 90 grados: lo que los comentarios de `tests/_corpus.py` afirman, medido por
        correlacion normalizada de una plantilla reducida a 1/8 (ML0) o 1/4 (braqui)."""
        if not _hay_peliculas():
            pytest.skip("no hay carpeta de peliculas reales en esta maquina (HI-0)")

        def gris(clave, escala):
            return cv2.resize(cv2.imread(_corpus.pelicula(clave), cv2.IMREAD_GRAYSCALE), None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)

        def mejor(pagina, plantilla):
            r = cv2.matchTemplate(pagina, plantilla, cv2.TM_CCOEFF_NORMED)
            _, maximo, _, lugar = cv2.minMaxLoc(r)
            return maximo, lugar

        correlacion, lugar = mejor(gris("EPSON027", 1 / 8), gris("ML0", 1 / 8))
        assert correlacion > 0.995 and abs(lugar[0] * 8 - 8) <= 16 and abs(lugar[1] * 8 - 8) <= 16, f"ML0 no es un recorte de EPSON027 ({correlacion:.4f}, {lugar})"
        otras = max(mejor(gris(c, 1 / 8), gris("ML0", 1 / 8))[0] for c in ("EPSON028", "EPSON029", "EPSON030"))
        assert otras < 0.97, "ML0 se parece a otra pagina tanto como a EPSON027: la prueba no distingue"
        pagina = cv2.rotate(gris("EPSON031", 1 / 4), cv2.ROTATE_90_COUNTERCLOCKWISE)
        assert mejor(pagina, gris("BRAQUI_00_JPG", 1 / 4))[0] > 0.995, "braqui_00.JPG no es un recorte de EPSON031 girado 90 grados"
        assert mejor(pagina, gris("BRAQUI_00_JPEG", 1 / 4))[0] > 0.99, "braqui_00.jpeg no sale de EPSON031 girado 90 grados"

    def test_las_copias_de_braqui_del_repo_son_las_del_corpus(self):
        if not _hay_peliculas():
            pytest.skip("no hay carpeta de peliculas reales en esta maquina (HI-0)")
        for clave, nombre in _corpus.COPIAS_EN_EL_REPO.items():
            assert _md5(DATOS / nombre) == _md5(_corpus.pelicula(clave)), f"tests/datos/{nombre} difiere de la del corpus ({clave})"

    def test_pelicula_devuelve_la_ruta_o_None_si_no_esta(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_corpus, "PELICULAS_RAIZ", str(tmp_path))
        assert _corpus.pelicula("ML0") is None
        (tmp_path / "ML0.JPG").write_bytes(b"x")
        assert _corpus.pelicula("ML0") == str(tmp_path / "ML0.JPG")
        with pytest.raises(KeyError):
            _corpus.pelicula("no_declarada")

    def test_pelicula_no_devuelve_una_carpeta_con_el_nombre_de_la_pelicula(self, tmp_path, monkeypatch):
        """Una CARPETA llamada como la pelicula no es la pelicula: `pelicula()` devuelve None (no una ruta que Image.open no podria abrir), igual que la regla de PR.0."""
        monkeypatch.setattr(_corpus, "PELICULAS_RAIZ", str(tmp_path))
        os.makedirs(tmp_path / "ML0.JPG")
        assert _corpus.pelicula("ML0") is None
        assert peliculas_que_faltan(str(tmp_path), {"ML0": "ML0.JPG"}) == ["ML0"], "la regla y `pelicula()` dicen lo mismo de una carpeta"
        os.rmdir(tmp_path / "ML0.JPG")
        (tmp_path / "ML0.JPG").write_bytes(b"x")
        assert _corpus.pelicula("ML0") == str(tmp_path / "ML0.JPG")

    def test_el_registro_de_peliculas_no_toca_el_de_las_series(self):
        """La regla de PR.0 de las series (carpetas) y la de las peliculas (archivos) son registros distintos; el acoplamiento de test_a0 sigue."""
        series = _corpus.todas_las_series_declaradas()
        assert set(series) == set(_corpus.CATPHAN) | set(_corpus.CORPUS_HOSPITAL)
        assert not set(series) & set(_corpus.todas_las_peliculas_declaradas())
        assert set(_catphan_oro.N_ARCHIVOS) == set(_corpus.CATPHAN)


# ============================================================================================================================
# 2. EL GENERADOR MENSUAL: determinismo y formatos
# ============================================================================================================================
FORMATOS = [("jpeg", 8, False), ("png", 8, False), ("png", 8, True), ("tiff", 8, False), ("tiff", 8, True),
            ("tiff", 16, False), ("tiff", 16, True), ("tiff", 16, "sin_pelicula")]


def _id_formato(f):
    formato, bits, alfa = f
    return f"{formato}{bits}{'-alfa' if alfa is True else '-alfa_sin_pelicula' if alfa else ''}"


def _generar_formato(f, **kw):
    formato, bits, alfa = f
    base = dict(variante="L", theta_deg=0.6, seed=3, dpi=DPI_PRUEBA)
    base.update(kw)
    return GM.generar(formato, bits=bits, alfa=alfa, **base)


class TestMensualDeterminismoYFormatos:
    @pytest.mark.parametrize("f", FORMATOS, ids=_id_formato)
    def test_dos_llamadas_dan_los_mismos_bytes(self, f):
        a, b = _generar_formato(f), _generar_formato(f)
        assert a.datos == b.datos
        assert len(a.datos) > 1000
        assert np.array_equal(a.imagen, b.imagen)

    def test_otra_semilla_da_otro_ruido_y_solo_el_ruido(self):
        a, b = GM.generar("png", seed=1, dpi=DPI_PRUEBA), GM.generar("png", seed=2, dpi=DPI_PRUEBA)
        assert a.datos != b.datos
        dif = np.abs(a.imagen.astype(int) - b.imagen.astype(int))
        assert 0.5 < dif.mean() < 4.0                                   # dos ruidos de sigma 1.5: diferencia media ~1.7 niveles
        assert a.verdad.resumen() == b.verdad.resumen()                 # la verdad no depende de la semilla

    def test_sin_ruido_la_semilla_no_importa(self):
        a = GM.generar("png", seed=1, ruido=0, dpi=DPI_PRUEBA)
        b = GM.generar("png", seed=99, ruido=0, dpi=DPI_PRUEBA)
        assert a.datos == b.datos

    def test_el_ruido_tiene_la_sigma_del_modelo(self):
        con = GM.generar_arreglo(seed=5, dpi=DPI_PRUEBA, tinta=False)[0].astype(float)
        sin = GM.generar_arreglo(seed=5, dpi=DPI_PRUEBA, tinta=False, ruido=0.0)[0].astype(float)
        residuo = (con - sin)[:, 200:420, :].ravel()                    # lejos del borde del campo no hay saturacion que recorte el ruido
        assert 1.3 < residuo.std() < 1.7                                # sigma 1.5 (el redondeo suma ~0.29)
        assert abs(residuo.mean()) < 0.1

    @pytest.mark.parametrize("f", FORMATOS, ids=_id_formato)
    def test_el_archivo_es_del_formato_pedido(self, f):
        formato, bits, alfa = f
        p = _generar_formato(f)
        assert (p.formato, p.bits, p.alfa, p.dpi) == (formato, bits, alfa, DPI_PRUEBA)
        assert p.verdad.parametros["formato"] == formato and p.verdad.parametros["bits"] == bits and p.verdad.parametros["alfa"] == alfa
        im = Image.open(io.BytesIO(p.datos))
        assert im.format == formato.upper()
        assert im.size == (p.verdad.ancho, p.verdad.alto)
        assert tuple(round(x) for x in im.info["dpi"]) == (DPI_PRUEBA, DPI_PRUEBA)            # declara la resolucion con que se genero
        if formato == "jpeg":
            assert im.mode == "RGB"
            assert JpegImagePlugin.get_sampling(im) == 2                                       # 4:2:0
            assert im.quantization[0][0] == 2 and im.quantization[0][1] == 1                   # la tabla de luminancia de calidad 95
        elif formato == "png":
            assert im.mode == ("RGBA" if alfa else "RGB")
        elif bits == 8:
            assert im.mode == ("RGBA" if alfa else "RGB")
        else:
            import tifffile
            lectura = tifffile.imread(io.BytesIO(p.datos))
            assert lectura.dtype == np.uint16 and lectura.shape == (p.verdad.alto, p.verdad.ancho, 4 if alfa else 3)

    @pytest.mark.parametrize("f", FORMATOS, ids=_id_formato)
    def test_lo_que_se_lee_del_archivo_es_el_arreglo_que_se_codifico(self, f):
        formato, bits, alfa = f
        p = _generar_formato(f)
        lectura = cv2.imdecode(np.frombuffer(p.datos, np.uint8), cv2.IMREAD_UNCHANGED)           # BGR(A), tal cual esta en el archivo
        assert lectura.dtype == (np.uint16 if bits == 16 else np.uint8)
        assert lectura.shape == p.imagen.shape
        if formato == "jpeg":
            assert np.abs(lectura.astype(float) - p.imagen.astype(float)).mean() < 4.0           # con perdida, pero fiel
        else:
            assert np.array_equal(lectura, p.imagen)                                             # sin perdida

    def test_el_tiff_de_16_bits_es_la_misma_pelicula_con_mas_resolucion(self):
        a8 = GM.generar("tiff", bits=8, seed=4, dpi=DPI_PRUEBA, ruido=0).imagen.astype(float)
        a16 = GM.generar("tiff", bits=16, seed=4, dpi=DPI_PRUEBA, ruido=0).imagen.astype(float)
        assert 40000 < a16.max() <= 65535 and abs(a16.max() - 257 * a8.max()) <= 129        # el verde virgen (174 niveles) llega a ~44700 de 65535
        assert np.abs(a16 / 257.0 - a8).max() <= 0.5 + 1e-9                                      # 257 = 65535 / 255: el mismo valor, cuantizado mas fino
        assert len(np.unique(a16)) > 4 * len(np.unique(a8))

    def test_alfa_opaco_y_alfa_sin_pelicula(self):
        opaco = GM.generar("tiff", alfa=True, variante="L", theta_deg=1.0, dpi=DPI_PRUEBA).imagen
        assert opaco.shape[2] == 4 and (opaco[:, :, 3] == 255).all()
        transp = GM.generar("tiff", alfa="sin_pelicula", variante="L", theta_deg=1.0, dpi=DPI_PRUEBA, ruido=0)
        a = transp.imagen[:, :, 3]
        fraccion = float((a == 0).mean())
        assert 0.002 < fraccion < 0.05, "el recorte suelto de una pelicula girada 1 grado trae cuñas de fondo del escaner en las esquinas"
        assert (a[a == 0].size + (a == 255).sum()) == a.size
        assert (transp.imagen[a == 0][:, :3] == 250).all()                                       # lo transparente es el blanco del escaner
        assert (transp.imagen[a == 255][:, :3] != 250).any()
        ajustado = GM.generar("tiff", alfa="sin_pelicula", variante="A", theta_deg=1.0, dpi=DPI_PRUEBA).imagen
        assert (ajustado[:, :, 3] == 255).all(), "el recorte ajustado (inscrito en la pelicula) no trae fondo"

    def test_las_combinaciones_invalidas_se_rechazan(self):
        with pytest.raises(ValueError):
            GM.generar("png", bits=16, dpi=DPI_PRUEBA)
        with pytest.raises(ValueError):
            GM.generar("jpeg", alfa=True, dpi=DPI_PRUEBA)
        with pytest.raises(ValueError):
            GM.generar("tiff", bits=12, dpi=DPI_PRUEBA)
        with pytest.raises(ValueError):
            GM.generar("tiff", alfa="semitransparente", dpi=DPI_PRUEBA)
        with pytest.raises(ValueError):
            GM.codificar(np.zeros((4, 4, 3), np.uint8), "bmp")
        with pytest.raises(ValueError, match="solo guarda 8 bits"):
            GM.codificar(np.zeros((4, 4, 3), np.uint16), "png")                                        # `generar` lo ataja antes, pero `codificar` tiene su propia guarda
        with pytest.raises(ValueError, match="no lleva canal alfa"):
            GM.codificar(np.zeros((4, 4, 4), np.uint8), "jpeg")

    def test_la_salida_no_depende_del_tamano_del_bloque_de_filas(self):
        a = GM.generar_arreglo(variante="L", theta_deg=0.7, seed=6, dpi=DPI_PRUEBA, defectos=[dict(tipo="rayon_v", u_mm=10.0, largo_mm=50.0, valor=240.0)],
                               filas_por_bloque=37)[0]
        b = GM.generar_arreglo(variante="L", theta_deg=0.7, seed=6, dpi=DPI_PRUEBA, defectos=[dict(tipo="rayon_v", u_mm=10.0, largo_mm=50.0, valor=240.0)],
                               filas_por_bloque=100000)[0]
        assert np.array_equal(a, b)


# ============================================================================================================================
# 3. EL GENERADOR MENSUAL: la verdad cuadra con la imagen
# ============================================================================================================================
def cruces_al_nivel(perfil, nivel):
    """Posiciones fraccionarias (en indices) del primer cruce ascendente y del ultimo descendente de `nivel` en un perfil, por interpolacion
    lineal entre los dos pixeles que lo rodean. Es la integracion INDEPENDIENTE de la prueba: no usa ninguna funcion del modelo."""
    p = np.asarray(perfil, float)
    idx = np.where(p >= nivel)[0]
    i, j = idx[0], idx[-1]
    xi = (i - 1) + (nivel - p[i - 1]) / (p[i] - p[i - 1])
    xd = j + (p[j] - nivel) / (p[j] - p[j + 1])
    return xi, xd


def ancho_al_50(perfil, px_mm):
    """Ancho (mm) del perfil al 50 % de su maximo."""
    a, b = cruces_al_nivel(perfil, 0.5 * np.max(perfil))
    return (b - a) * px_mm


def media_recortada(valores, fraccion=0.1):
    """Media del 80 % central (se descarta el `fraccion` de cada extremo): resolucion de sub-nivel (el ruido del escaner dithera el redondeo a 8 bits) y
    robusta al polvo y a las marcas."""
    v = np.sort(np.asarray(valores, float).ravel())
    k = int(fraccion * len(v))
    return float(v[k:len(v) - k].mean())


def cupula_a_40_mm(bgr, mm_por_px):
    """Cupula (en %) de una pelicula: la dosis relativa a 40 mm del centro del campo frente a la del centro, por PROMEDIO ANULAR del canal AZUL (que es lineal
    en la dosis: la dosis relativa es (virgen - azul) / (virgen - meseta)). Integracion independiente del generador: ni el modelo ni sus funciones.
      - la pelicula es lo que no es el blanco del escaner (verde < 235); su nivel VIRGEN se mide en SUS cuatro esquinas (cambia de una pelicula a otra);
      - el centro del campo es el centroide de la region mucho mas oscura que la mitad entre la virgen y la meseta (la componente mas grande);
      - el centro es el disco entre 3 y 8 mm (sin la marca central) y los 40 mm son la corona entre 36 y 44 mm, las dos con media recortada: miles de pixeles.
    Con cuatro ventanas sueltas (la medicion cruda de la revision, que fijaba ademas la virgen en 82) se daba de +4.8 a -11.5 %: un nivel de azul son 2.3 % de dosis."""
    filas, cols = np.where(bgr[:, :, 1] < 235)
    x0, x1 = (int(v) for v in np.percentile(cols, [0.05, 99.95]))
    y0, y1 = (int(v) for v in np.percentile(filas, [0.05, 99.95]))
    azul = bgr[y0:y1 + 1, x0:x1 + 1, 0].astype(float)
    alto, ancho = azul.shape
    p, m = int(round(4.0 / mm_por_px)), int(round(2.0 / mm_por_px))
    esquinas = [azul[m:m + p, m:m + p], azul[m:m + p, ancho - m - p:ancho - m], azul[alto - m - p:alto - m, m:m + p], azul[alto - m - p:alto - m, ancho - m - p:ancho - m]]
    virgen = media_recortada(np.concatenate([e.ravel() for e in esquinas]))
    nivel = 0.5 * (virgen + float(np.percentile(azul, 5)))
    _, _, estadisticas, centroides = cv2.connectedComponentsWithStats((azul < nivel).astype(np.uint8), connectivity=8)
    cx, cy = centroides[1 + int(np.argmax(estadisticas[1:, cv2.CC_STAT_AREA]))]
    yy, xx = np.mgrid[0:alto, 0:ancho]
    r = np.hypot(xx - cx, yy - cy) * mm_por_px
    centro = media_recortada(azul[(r > 3.0) & (r < 8.0)])
    anillo = media_recortada(azul[(r >= 36.0) & (r < 44.0)])
    return 100.0 * ((virgen - anillo) / (virgen - centro) - 1.0)


CONFIGURACIONES = [(0.0, 0.0), (0.02, 0.0), (0.0, -3.5), (0.02, -3.5), (0.05, -5.0), (-0.03, -2.0)]    # (beta, cupula_pct_40mm)


def _id_config(c):
    return f"beta{c[0]:+g}_cupula{c[1]:+g}"


class TestMensualLaVerdadCuadraConLaImagen:
    @pytest.mark.parametrize("config", CONFIGURACIONES, ids=_id_config)
    def test_el_FWHM_de_la_dosis_sin_ruido_medido_por_integracion_independiente_coincide_con_la_verdad(self, config):
        """Filas (crossplane) y columnas (inplane) del mapa de dosis sin ruido: el cruce del 50 % interpolado sobre el arreglo da el FWHM de la verdad
        a +-0.01 mm en 5 filas y 5 columnas, tambien con la pendiente beta y con la cupula."""
        beta, cupula = config
        D, verdad = GM.mapa_dosis("A", 0.0, DPI_MEDIDA, beta=beta, cupula_pct_40mm=cupula)
        px = 25.4 / DPI_MEDIDA
        cx, cy = verdad.centro_campo_px
        n = 0
        for v_mm in (-40.0, -20.0, 0.0, 20.0, 40.0):
            iy = int(round(cy + v_mm / px))
            v = (iy - cy) * px
            medido = ancho_al_50(D[iy, :], px)
            assert medido == pytest.approx(verdad.fwhm_x_en(v), abs=0.01), f"fila v={v:.3f} mm"
            n += 1
        for u_mm in (-38.0, -20.0, 0.0, 20.0, 38.0):
            ix = int(round(cx + u_mm / px))
            u = (ix - cx) * px
            medido = ancho_al_50(D[:, ix], px)
            assert medido == pytest.approx(verdad.fwhm_y_en(u), abs=0.01), f"columna u={u:.3f} mm"
            n += 1
        assert n == 10

    def test_el_FWHM_en_los_ejes_centrales_es_100_por_99_con_y_sin_las_extensiones(self):
        for beta, cupula in CONFIGURACIONES:
            v = GM.generar_arreglo(dpi=40, beta=beta, cupula_pct_40mm=cupula)[1]
            assert v.FWHM_x == pytest.approx(100.0, abs=1e-9)
            assert v.FWHM_y == pytest.approx(99.0, abs=1e-9)
            assert v.bordes_rad["R"] == pytest.approx(-v.bordes_rad["L"], abs=1e-9)
            assert v.bordes_rad["B"] == pytest.approx(-v.bordes_rad["T"], abs=1e-9)
            assert v.bordes_rad["R"] == pytest.approx(50.0, abs=1e-9)
            assert v.bordes_rad["B"] == pytest.approx(49.5, abs=1e-9)

    def test_con_beta_el_FWHM_crossplane_varia_linealmente_con_la_posicion(self):
        beta = 0.04
        v = GM.generar_arreglo(dpi=40, beta=beta)[1]
        base = v.fwhm_x_en(0.0)
        for pos in (-40.0, -15.5, 7.0, 40.0):
            assert v.fwhm_x_en(pos) - base == pytest.approx(beta * pos, abs=1e-4)           # lineal sin cupula: w_x(v) = w_x0 + beta v (la cola en y cambia ~5e-6 mm)
        assert v.fwhm_x_en(40.0) - v.fwhm_x_en(-40.0) == pytest.approx(80 * beta, abs=1e-4)
        plano = GM.generar_arreglo(dpi=40)[1]
        assert plano.fwhm_x_en(40.0) == pytest.approx(plano.fwhm_x_en(-40.0), abs=1e-9)    # con beta = 0 todas las filas miden lo mismo
        con_cupula = GM.generar_arreglo(dpi=40, beta=beta, cupula_pct_40mm=-3.5)[1]
        for pos in (-40.0, 40.0):
            assert con_cupula.fwhm_x_en(pos) - con_cupula.fwhm_x_en(0.0) == pytest.approx(beta * pos, abs=0.05)      # con cupula la cupula en v cambia el nivel: ~0.025 mm

    def test_el_FWHM_por_banda_se_ve_en_la_imagen_cuando_beta_no_es_cero(self):
        beta = 0.04
        D, verdad = GM.mapa_dosis("A", 0.0, DPI_MEDIDA, beta=beta)
        px = 25.4 / DPI_MEDIDA
        cy = verdad.centro_campo_px[1]
        arriba = ancho_al_50(D[int(round(cy - 40.0 / px)), :], px)
        abajo = ancho_al_50(D[int(round(cy + 40.0 / px)), :], px)
        assert abajo - arriba == pytest.approx(80 * beta, abs=0.03), "la fila de abajo (v>0) es mas ancha: w_x crece con v"
        bandas = verdad.fwhm_x_por_banda(np.arange(-40, 41, 10))
        assert len(bandas) == 9 and bandas[40.0] - bandas[-40.0] == pytest.approx(80 * beta, abs=1e-4)

    @pytest.mark.parametrize("pct", [-2.0, -3.5, -5.0])
    def test_la_cupula_baja_la_dosis_a_40_mm_lo_que_dice(self, pct):
        D, verdad = GM.mapa_dosis("A", 0.0, DPI_MEDIDA, cupula_pct_40mm=pct)
        px = 25.4 / DPI_MEDIDA
        cx, cy = verdad.centro_campo_px
        iy, ix0 = int(round(cy)), int(round(cx))
        centro = D[iy, ix0]
        a40 = D[iy, int(round(cx + 40.0 / px))]
        b40 = D[iy, int(round(cx - 40.0 / px))]
        v40 = D[int(round(cy + 40.0 / px)), ix0]
        for valor in (a40, b40, v40):
            assert valor / centro - 1.0 == pytest.approx(pct / 100.0, abs=4e-4)
        assert centro == pytest.approx(1.0, abs=1e-4)
        perfil = D[iy, int(round(cx - 40.0 / px)):int(round(cx + 40.0 / px)) + 1]
        assert perfil.argmax() == pytest.approx(len(perfil) / 2, abs=2), "es una cupula: el maximo esta en el centro"

    def test_con_signo_contrario_no_es_una_cupula_sino_cuernos(self):
        D, verdad = GM.mapa_dosis("A", 0.0, DPI_MEDIDA, cupula_pct_40mm=+3.5)
        px = 25.4 / DPI_MEDIDA
        cx, cy = verdad.centro_campo_px
        iy = int(round(cy))
        assert D[iy, int(round(cx + 40.0 / px))] > D[iy, int(round(cx))]                          # a 40 mm hay MAS dosis que en el centro
        assert verdad.FWHM_x == pytest.approx(100.0, abs=1e-9)                                     # y los ejes centrales siguen midiendo 100 x 99

    def test_los_limites_de_la_cupula_declarados_son_los_del_plan(self):
        """Solo lo que dice: las dos constantes del modulo son las de PF.0 OBJETIVO 2 (-2 a -5 % a 40 mm). Que ese rango sea el de las peliculas REALES lo comprueba
        `test_la_cupula_de_las_peliculas_reales_a_40_mm_esta_en_el_rango_que_declara_el_generador`, y que el generador lo ponga, `test_el_metodo_anular_mide_la_cupula_que_pone_el_generador`."""
        assert (GM.CUPULA_REAL_MIN_PCT, GM.CUPULA_REAL_MAX_PCT) == (-2.0, -5.0)

    @pytest.mark.parametrize("pct", [0.0, GM.CUPULA_REAL_MIN_PCT, -3.5, GM.CUPULA_REAL_MAX_PCT, +3.5])
    @pytest.mark.parametrize("variante,theta", [("A", 0.0), ("L", 0.5)])
    def test_el_metodo_anular_mide_la_cupula_que_pone_el_generador(self, pct, variante, theta):
        """El metodo que mide las peliculas reales (promedio anular del azul) devuelve, sobre las sinteticas, la cupula que el generador pone: +-0.4 puntos, y con signo
        (+3.5 % son cuernos). Sin esto la medicion de las reales no se podria creer."""
        img, _ = GM.generar_arreglo(variante=variante, theta_deg=theta, dpi=150, seed=3, cupula_pct_40mm=pct)
        assert cupula_a_40_mm(np.asarray(img), 25.4 / 150) == pytest.approx(pct, abs=0.4)

    def test_la_cupula_de_las_peliculas_reales_a_40_mm_esta_en_el_rango_que_declara_el_generador(self):
        """PF.0 pide una meseta en cupula '-2 a -5 % a 40 mm, como las peliculas reales'. Medido en las diez peliculas mensuales del plan (azul, lineal en la dosis;
        nivel virgen y meseta de CADA pelicula; promedio anular): de -1.6 a -5.7 %, media -4.1 %. Todas son cupula (ninguna con cuernos), ninguna se aparta mas de 1.5
        puntos del rango declarado y su media cae DENTRO de el."""
        if not _hay_peliculas():
            pytest.skip("no hay carpeta de peliculas reales en esta maquina (HI-0)")
        valores = {}
        for clave in MENSUALES_DEL_PLAN:
            ruta = _corpus.pelicula(clave)
            if ruta is None:
                pytest.fail(f"{clave}: la carpeta de peliculas existe y la pelicula no esta ({MENSUALES_DEL_PLAN[clave]})")
            valores[clave] = cupula_a_40_mm(cv2.imread(ruta, cv2.IMREAD_COLOR), 25.4 / 600)
        asi = ", ".join(f"{k} {v:+.2f}" for k, v in valores.items())
        assert len(valores) == 10
        assert GM.CUPULA_REAL_MAX_PCT <= np.mean(list(valores.values())) <= GM.CUPULA_REAL_MIN_PCT, f"la media de las peliculas reales no cae en el rango declarado: {asi}"
        assert max(valores.values()) < 0.0, f"alguna pelicula real tiene cuernos y no cupula: {asi}"
        assert all(GM.CUPULA_REAL_MAX_PCT - 1.5 <= v <= GM.CUPULA_REAL_MIN_PCT + 1.5 for v in valores.values()), f"alguna se aparta del rango mas de 1.5 puntos: {asi}"

    @pytest.mark.parametrize("config", [(0.0, 0.0), (0.02, -3.5), (0.05, -5.0)], ids=_id_config)
    def test_los_FWHM_por_capa_medidos_en_el_TIFF_de_16_bits_coinciden_con_la_verdad_de_la_respuesta(self, config):
        """El TIFF de 16 bits sin ruido guarda la respuesta de cada capa con 1/257 de nivel: se invierte (virgen - crudo)/(virgen - meseta) y el
        cruce del 50 % del perfil de CADA capa coincide con los bordes que predice el generador, +-0.01 mm."""
        beta, cupula = config
        p = GM.generar("tiff", bits=16, variante="A", theta_deg=0.0, seed=1, dpi=DPI_MEDIDA, ruido=0, tinta=False, beta=beta, cupula_pct_40mm=cupula)
        img = cv2.imdecode(np.frombuffer(p.datos, np.uint8), cv2.IMREAD_UNCHANGED)
        virgen, meseta = GM.CALIB["virgen_bgr"], GM.CALIB["meseta_bgr"]
        px = 25.4 / DPI_MEDIDA
        cx, cy = p.verdad.centro_campo_px
        n = 0
        for k, capa in enumerate("BGR"):
            plano = (virgen[k] - img[:, :, k].astype(float) / 257.0) / (virgen[k] - meseta[k])          # g_c(D)
            for v_mm in (-30.0, 0.0, 30.0):
                iy = int(round(cy + v_mm / px))
                v = (iy - cy) * px
                assert ancho_al_50(plano[iy, :], px) == pytest.approx(p.verdad.fwhm_x_en(v, capa), abs=0.01), f"capa {capa}, fila v={v:.2f}"
                n += 1
            for u_mm in (-30.0, 0.0, 30.0):
                ix = int(round(cx + u_mm / px))
                u = (ix - cx) * px
                assert ancho_al_50(plano[:, ix], px) == pytest.approx(p.verdad.fwhm_y_en(u, capa), abs=0.01), f"capa {capa}, columna u={u:.2f}"
                n += 1
        assert n == 18

    def test_solo_el_azul_es_lineal_en_la_dosis_y_las_otras_capas_miden_mas_ancho(self):
        verdad = GM.generar_arreglo(dpi=40)[1]
        c = verdad.capas
        assert (c["B"].lineal, c["G"].lineal, c["R"].lineal) == (True, False, False)
        assert (c["B"].k, c["G"].k, c["R"].k) == (0.0, 0.7, 3.6)
        for lado in "LRTB":
            assert c["B"].bordes[lado] == pytest.approx(verdad.bordes_rad[lado], abs=1e-9), "el azul es la dosis"
        assert c["B"].FWHM_x == pytest.approx(verdad.FWHM_x, abs=1e-9)
        assert c["B"].FWHM_x < c["G"].FWHM_x < c["R"].FWHM_x
        assert c["B"].FWHM_y < c["G"].FWHM_y < c["R"].FWHM_y
        assert 0.5 < c["G"].FWHM_x - c["B"].FWHM_x < 1.5                                          # el verde mide ~+1.0 mm (el cuaderno vio +0.84)
        assert 3.5 < c["R"].FWHM_x - c["B"].FWHM_x < 5.0                                          # el rojo ~+4.4 mm (el cuaderno vio +4.15)
        assert c["R"].bordes["R"] > c["G"].bordes["R"] > c["B"].bordes["R"] > 0 > c["B"].bordes["L"] > c["G"].bordes["L"] > c["R"].bordes["L"]

    @pytest.mark.parametrize("variante,theta,config,desplazamiento", [("A", 0.0, (0.0, 0.0), None), ("A", 0.9, (0.04, -4.0), None), ("L", -1.0, (0.0, -3.5), None),
                                                                      ("C", 0.5, (0.02, 0.0), None), ("L", 0.3, (0.02, -2.0), (7.5, -3.25))])
    def test_la_imagen_es_la_dosis_del_mapa_en_el_azul_que_es_lineal(self, variante, theta, config, desplazamiento):
        """El canal azul del TIFF de 16 bits sin ruido es lineal en la dosis (virgen - (virgen - meseta) D): invertido da el mapa de dosis, en todos los
        pixeles de la pelicula, a 2e-4 (la cuantizacion de 16 bits). Une la imagen con el mapa y la verdad, con giro y con las dos extensiones."""
        beta, cupula = config
        p = GM.generar("tiff", bits=16, variante=variante, theta_deg=theta, seed=1, dpi=DPI_MEDIDA, ruido=0, tinta=False, beta=beta, cupula_pct_40mm=cupula,
                       alfa="sin_pelicula", desplazamiento_px=desplazamiento)
        img = cv2.imdecode(np.frombuffer(p.datos, np.uint8), cv2.IMREAD_UNCHANGED)
        D, verdad = GM.mapa_dosis(variante, theta, DPI_MEDIDA, beta=beta, cupula_pct_40mm=cupula, desplazamiento_px=desplazamiento)
        v, m = GM.CALIB["virgen_bgr"][0], GM.CALIB["meseta_bgr"][0]
        dosis_de_la_imagen = (v - img[:, :, 0].astype(float) / 257.0) / (v - m)
        en_pelicula = img[:, :, 3] == 65535
        assert en_pelicula.mean() > 0.5
        assert np.abs(dosis_de_la_imagen - D)[en_pelicula].max() < 2e-4
        assert (verdad.ancho, verdad.alto) == (img.shape[1], img.shape[0])

    def test_generar_y_generar_arreglo_arman_la_misma_imagen_con_todas_las_opciones(self):
        opciones = dict(variante="L", theta_deg=0.8, seed=9, dpi=DPI_PRUEBA, ruido=0.7, tinta=True, fondo="blanco", beta=0.03, cupula_pct_40mm=-2.5,
                        desplazamiento_px=(4.0, -2.0), defectos=[dict(tipo="rayon_h", v_mm=10.0, largo_mm=40.0, valor=235.0)])
        placa = GM.generar("tiff", bits=16, **opciones)
        arreglo, verdad = GM.generar_arreglo(bits=16, **opciones)
        assert np.array_equal(placa.imagen, arreglo)
        assert placa.verdad.resumen() == verdad.resumen()
        sin_opciones = GM.generar_arreglo(bits=16, variante="L", theta_deg=0.8, seed=9, dpi=DPI_PRUEBA)[0]
        assert not np.array_equal(arreglo, sin_opciones)

    def test_la_verdad_en_el_cruce_de_diagonales_y_los_bordes_por_fila_y_columna(self):
        """La fila y la columna que pasan por el cruce de diagonales de las marcas luminosas (-0.6, 0.4 mm del centro de la radiacion) son las que miden los
        cuadernos y la app: su verdad es la del modelo en esa fila y esa columna, que con beta difiere de la de los ejes del campo."""
        beta = 0.03
        v = GM.generar_arreglo(dpi=DPI_PRUEBA, beta=beta, cupula_pct_40mm=-3.0)[1]
        assert v.centro_luz == (-0.6, 0.4)
        assert v.fwhm_x_en_el_cruce() == v.fwhm_x_en(0.4) and v.fwhm_y_en_el_cruce() == v.fwhm_y_en(-0.6)
        assert v.fwhm_x_en_el_cruce() - v.FWHM_x == pytest.approx(beta * 0.4, abs=2e-3)
        assert v.fwhm_x_en_el_cruce("R") == v.fwhm_x_en(0.4, "R") and v.fwhm_x_en_el_cruce("R") > v.fwhm_x_en_el_cruce("G") > v.fwhm_x_en_el_cruce("B")
        izq, der = v.bordes_fila_en(25.0)
        assert der - izq == pytest.approx(v.fwhm_x_en(25.0), abs=1e-12) and izq < 0 < der
        sup, inf = v.bordes_columna_en(-20.0, "G")
        assert inf - sup == pytest.approx(v.fwhm_y_en(-20.0, "G"), abs=1e-12) and sup < 0 < inf
        pel = v.esquinas_pelicula_px
        px = 25.4 / DPI_PRUEBA
        ancho_mm = np.hypot(pel["UR"][0] - pel["UL"][0], pel["UR"][1] - pel["UL"][1]) * px
        alto_mm = np.hypot(pel["DL"][0] - pel["UL"][0], pel["DL"][1] - pel["UL"][1]) * px
        assert (ancho_mm, alto_mm) == pytest.approx((115.0, 116.0), abs=1e-9), "la pelicula medida en la imagen es la de 115 x 116 mm, girada o no"

    def test_el_resumen_de_la_verdad_dice_lo_mismo_que_sus_campos(self):
        v = GM.generar_arreglo(variante="C", theta_deg=0.6, dpi=DPI_PRUEBA, beta=0.02, cupula_pct_40mm=-3.5)[1]
        r = v.resumen()
        assert (r["FWHM_x"], r["FWHM_y"]) == (v.FWHM_x, v.FWHM_y) and r["giro_deg"] == 0.6 and r["variante"] == "C" and r["dpi"] == DPI_PRUEBA
        assert (r["beta"], r["cupula_pct_40mm"]) == (0.02, -3.5) and r["centro_campo_px"] == v.centro_campo_px and r["marcas_px"] == v.marcas_px
        assert r["exceso"] == v.exceso and r["bordes_luz"] == v.bordes_luz and r["bordes_rad"] == v.bordes_rad
        assert set(r["capas"]) == {"B", "G", "R"} and r["capas"]["R"]["FWHM_x"] == v.capas["R"].FWHM_x and (r["ancho"], r["alto"]) == (v.ancho, v.alto)

    def test_la_verdad_por_columna_solo_vale_dentro_de_la_meseta(self):
        v = GM.generar_arreglo(dpi=40)[1]
        assert 40.0 < v.campo.limite_columna_mm() < 41.5
        v.fwhm_y_en(40.0)
        with pytest.raises(ValueError):
            v.fwhm_y_en(45.0)
        trapecio = GM.generar_arreglo(dpi=40, beta=0.05)[1]
        assert trapecio.campo.limite_columna_mm() < v.campo.limite_columna_mm() - 0.5, "con la pendiente beta el lado del trapecio entra antes"
        with pytest.raises(ValueError):
            trapecio.fwhm_y_en(40.5)

    def test_a_600_dpi_la_pelicula_mide_lo_que_la_real_y_la_verdad_cuadra(self):
        """Los argumentos por omision son los reales (600 dpi): una fila y una columna del mapa de dosis a la resolucion del escaner."""
        placa = GM.generar("png", variante="A", theta_deg=0.0, seed=1)
        assert placa.dpi == 600 and placa.verdad.dpi == 600
        assert (placa.verdad.ancho, placa.verdad.alto) == (2710, 2734)                              # el recorte ajustado de la pelicula de 115 x 116 mm
        px600 = 25.4 / 600
        assert placa.verdad.centro_campo_px == pytest.approx((57.3 / px600 - 3, 55.3 / px600 - 3), abs=1e-6), "el campo esta donde dice el modelo dentro de la pelicula"
        assert Image.open(io.BytesIO(placa.datos)).size == (2710, 2734)
        D, verdad = GM.mapa_dosis("A", 0.0, 600, beta=0.02, cupula_pct_40mm=-3.5)
        px = 25.4 / 600
        cx, cy = verdad.centro_campo_px
        iy = int(round(cy + 25.0 / px))
        assert ancho_al_50(D[iy, :], px) == pytest.approx(verdad.fwhm_x_en((iy - cy) * px), abs=0.01)
        ix = int(round(cx - 25.0 / px))
        assert ancho_al_50(D[:, ix], px) == pytest.approx(verdad.fwhm_y_en((ix - cx) * px), abs=0.01)

    def test_los_bordes_por_capa_siguen_a_las_extensiones(self):
        base = GM.generar_arreglo(dpi=40)[1]
        con = GM.generar_arreglo(dpi=40, beta=0.04, cupula_pct_40mm=-4.0)[1]
        assert con.fwhm_x_en(30.0, "G") > base.fwhm_x_en(30.0, "G") + 1.0
        assert con.fwhm_x_en(-30.0, "R") < base.fwhm_x_en(-30.0, "R") - 1.0
        assert con.fwhm_x_en(30.0, "B") - con.fwhm_x_en(-30.0, "B") == pytest.approx(60 * 0.04, abs=0.03)

    @pytest.mark.parametrize("variante,theta,config", [("A", 0.4, (0.02, -3.5)), ("A", 1.0, (0.0, 0.0)), ("L", 1.0, (0.05, -5.0)),
                                                       ("C", 1.0, (0.02, -2.0)), ("B", -0.8, (0.0, -3.5)), ("E", 0.5, (0.03, -3.0))])
    def test_con_la_pelicula_girada_la_verdad_vale_a_lo_largo_de_las_rectas_de_la_pelicula(self, variante, theta, config):
        """Se muestrea el mapa de dosis con interpolacion cubica a lo largo de las rectas de la PELICULA (no de la imagen): el FWHM sigue siendo el de la verdad."""
        beta, cupula = config
        D, verdad = GM.mapa_dosis(variante, theta, DPI_MEDIDA, beta=beta, cupula_pct_40mm=cupula)
        paso = 0.02
        n = 0
        for v in (-35.0, 0.0, 12.3, 35.0):
            us = np.arange(-70.0, 70.0001, paso)
            pts = np.array([verdad.mm_a_px(u, v) for u in us])
            perfil = map_coordinates(D, [pts[:, 1], pts[:, 0]], order=3, mode="nearest")
            assert ancho_al_50(perfil, paso) == pytest.approx(verdad.fwhm_x_en(v), abs=0.01), f"fila v={v}"
            n += 1
        for u in (-30.0, 0.0, 30.0):
            vs = np.arange(-70.0, 70.0001, paso)
            pts = np.array([verdad.mm_a_px(u, v) for v in vs])
            perfil = map_coordinates(D, [pts[:, 1], pts[:, 0]], order=3, mode="nearest")
            assert ancho_al_50(perfil, paso) == pytest.approx(verdad.fwhm_y_en(u), abs=0.01), f"columna u={u}"
            n += 1
        assert n == 7

    @pytest.mark.parametrize("variante", ["A", "L", "C", "D", "E"])
    @pytest.mark.parametrize("theta", [-0.7, 0.0, 0.4, 1.0])
    def test_el_giro_y_el_centro_del_campo_de_la_verdad_son_los_de_la_imagen(self, variante, theta):
        D, verdad = GM.mapa_dosis(variante, theta, DPI_MEDIDA)
        px = 25.4 / DPI_MEDIDA
        cx, cy = verdad.centro_campo_px
        ys, xs = np.nonzero(D >= 0.5)
        assert (xs.mean() - cx, ys.mean() - cy) == pytest.approx((0.0, 0.0), abs=0.25)           # el centroide de la region irradiada es el centro del campo

        def borde_superior(ix):
            col = D[:, ix]
            i = np.where(col >= 0.5)[0][0]
            return (i - 1) + (0.5 - col[i - 1]) / (col[i] - col[i - 1])
        x1, x2 = int(round(cx - 30 / px)), int(round(cx + 30 / px))
        angulo = np.degrees(np.arctan2(borde_superior(x2) - borde_superior(x1), x2 - x1))
        assert angulo == pytest.approx(theta, abs=0.02), "giro positivo = horario en pantalla: el borde superior baja hacia la derecha"
        assert verdad.giro_deg == theta

    @pytest.mark.parametrize("variante,theta,dpi", [("A", 0.4, 200), ("L", 1.0, 200), ("C", -0.7, 200)])
    def test_las_marcas_de_tinta_estan_donde_dice_la_verdad(self, variante, theta, dpi):
        img, verdad = GM.generar_arreglo(variante=variante, theta_deg=theta, seed=1, dpi=dpi, ruido=0)
        img = np.asarray(img).astype(float)
        px = 25.4 / dpi
        assert set(verdad.marcas_px) == {"UL", "UR", "DL", "DR", "C"}
        for nombre, (mx, my) in verdad.marcas_px.items():
            r = int(4.0 / px)
            x0, y0 = int(round(mx)) - r, int(round(my)) - r
            sub = img[y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1]
            mascara = (sub[:, :, 0] + sub[:, :, 1]) / 2 <= 12                                    # la tinta es 4 en todas las capas; la pelicula, mucho mas en B y G
            ys, xs = np.nonzero(mascara)
            assert (30 if nombre == "C" else 18) <= mascara.sum() <= (50 if nombre == "C" else 34), f"{nombre}: la tinta no es un punto de 0.5 mm de radio ({mascara.sum()} px)"
            assert (xs.mean() + x0 - mx, ys.mean() + y0 - my) == pytest.approx((0.0, 0.0), abs=0.3), nombre

    def test_la_geometria_de_las_marcas_es_la_del_modelo(self):
        verdad = GM.generar_arreglo(dpi=40)[1]
        assert verdad.marcas_mm["UL"] == pytest.approx((-50.4, -49.5)) and verdad.marcas_mm["DR"] == pytest.approx((49.2, 50.3))
        assert verdad.marcas_mm["C"] == pytest.approx((-0.3, 0.2))
        assert verdad.centro_luz == (-0.6, 0.4)
        assert verdad.exceso == pytest.approx(dict(L=-0.4, R=0.8, T=0.0, B=-0.8), abs=1e-9)
        assert verdad.centro_rad_menos_luz == pytest.approx((0.6, -0.4), abs=1e-9)
        assert verdad.reticulo_menos_luz == (0.3, -0.2)

    def test_los_clics_son_los_enteros_mas_cercanos_a_las_marcas_y_van_en_el_orden_del_cuaderno(self):
        verdad = GM.generar_arreglo(variante="C", theta_deg=0.4, dpi=DPI_PRUEBA)[1]
        for nombre, (x, y) in verdad.clics().items():
            assert (x, y) == (int(round(verdad.marcas_px[nombre][0])), int(round(verdad.marcas_px[nombre][1])))
        cuaderno = verdad.clics_del_cuaderno()
        orden = [verdad.clics()[n] for n in ("UL", "UR", "C", "DR", "DL")]
        assert cuaderno == orden

    @pytest.mark.parametrize("variante,esperado_600", [("C", (3300, 3300)), ("B", (3300, 3300)), ("D", (4400, 3300)), ("E", (3300, 3300))])
    def test_las_paginas_miden_lo_que_dice_el_encuadre_y_escalan_con_el_dpi(self, variante, esperado_600):
        for dpi in (60, 150):
            img, verdad = GM.generar_arreglo(variante=variante, dpi=dpi, tinta=False)
            ancho, alto = round(esperado_600[0] * dpi / 600), round(esperado_600[1] * dpi / 600)
            assert (verdad.ancho, verdad.alto) == (ancho, alto) and img.shape[:2] == (alto, ancho)

    def test_los_recortes_ajustado_y_suelto_son_la_pelicula_y_su_caja(self):
        _, ajustado = GM.generar_arreglo(variante="A", theta_deg=1.0, dpi=DPI_MEDIDA)
        _, suelto = GM.generar_arreglo(variante="L", theta_deg=1.0, dpi=DPI_MEDIDA)
        px = 25.4 / DPI_MEDIDA
        assert suelto.ancho > ajustado.ancho and suelto.alto > ajustado.alto
        assert suelto.ancho * px > 115.0 and suelto.alto * px > 116.0                              # la caja envolvente de una pelicula girada es mayor que la pelicula
        assert ajustado.ancho * px < 115.0 and ajustado.alto * px < 116.0                          # el rectangulo inscrito es menor
        _, sin_giro = GM.generar_arreglo(variante="A", theta_deg=0.0, dpi=DPI_MEDIDA)
        assert 113.0 < sin_giro.ancho * px <= 115.0 and 114.0 < sin_giro.alto * px <= 116.0          # la pelicula menos el margen de 3 px por lado del recorte ajustado

    def test_un_defecto_de_rayon_se_pinta_donde_se_pide_y_el_fondo_pelicula_la_prolonga(self):
        base = GM.generar_arreglo(variante="L", theta_deg=0.8, dpi=DPI_PRUEBA, ruido=0, tinta=False)
        con = GM.generar_arreglo(variante="L", theta_deg=0.8, dpi=DPI_PRUEBA, ruido=0, tinta=False,
                                 defectos=[dict(tipo="rayon_v", u_mm=20.0, largo_mm=60.0, valor=240.0, ancho_px=3),
                                           dict(tipo="rayon_h", v_mm=-15.0, largo_mm=50.0, valor=230.0, ancho_px=2)])
        dif = np.any(np.asarray(base[0]) != np.asarray(con[0]), axis=2)
        assert 100 < dif.sum() < 1500
        cx, cy = con[1].centro_campo_px
        px = 25.4 / DPI_PRUEBA
        assert (np.asarray(con[0])[int(cy), int(round(cx + 20.0 / px)):int(round(cx + 20.0 / px)) + 3, :] == 240).all()
        with pytest.raises(ValueError):
            GM.generar_arreglo(dpi=DPI_PRUEBA, defectos=[dict(tipo="mancha")])
        sin_fondo = np.asarray(GM.generar_arreglo(variante="L", theta_deg=1.0, dpi=DPI_PRUEBA, ruido=0, tinta=False, fondo="pelicula")[0])
        assert not (sin_fondo == 250).all(axis=2).any(), "con fondo='pelicula' la pelicula se prolonga: no hay blanco del escaner"
        assert (np.asarray(GM.generar_arreglo(variante="L", theta_deg=1.0, dpi=DPI_PRUEBA, ruido=0, tinta=False)[0]) == 250).all(axis=2).any()

    @pytest.mark.parametrize("defecto", [dict(tipo="rayon_v", u_mm=20.0, largo_mm=60.0, valor=240.0, ancho_px=3), dict(tipo="rayon_v", u_mm=-15.0, largo_mm=40.0, valor=235.0),
                                         dict(tipo="rayon_h", v_mm=-15.0, largo_mm=50.0, valor=230.0, ancho_px=2), dict(tipo="rayon_h", v_mm=12.0, largo_mm=30.0, valor=225.0, ancho_px=4),
                                         dict(tipo="rayon_h", v_mm=8.0, largo_mm=20.0, valor=220.0)],
                             ids=["vertical_a_la_derecha_3px", "vertical_a_la_izquierda_2px_por_omision", "horizontal_arriba_2px", "horizontal_abajo_4px", "horizontal_abajo_2px_por_omision"])
    def test_los_rayones_cubren_exactamente_lo_que_dicen(self, defecto):
        """Un rayon cubre EXACTAMENTE el rectangulo que dice: `u_mm` (vertical) a la derecha (+) o a la izquierda (-) del centro del campo, `v_mm` (horizontal) por debajo (+) o
        por encima (-); `largo_mm` centrado en el campo; `ancho_px` de grosor (2 por omision); el valor, en las tres capas. El conjunto de pixeles que cambia es el rectangulo, ni uno mas
        ni uno menos. (A.2 usara rayones sobre la pelicula, 'un rayon de 8 px -99 mm': el signo de la posicion y la longitud tienen que ser las que se piden.)"""
        base, verdad = GM.generar_arreglo(variante="L", theta_deg=0.8, dpi=DPI_PRUEBA, ruido=0, tinta=False)
        con, _ = GM.generar_arreglo(variante="L", theta_deg=0.8, dpi=DPI_PRUEBA, ruido=0, tinta=False, defectos=[defecto])
        px = 25.4 / DPI_PRUEBA
        cx, cy = verdad.centro_campo_px
        esperado = np.zeros(base.shape[:2], bool)
        grosor = defecto.get("ancho_px", 2)
        mitad = defecto["largo_mm"] / 2.0 / px
        if defecto["tipo"] == "rayon_v":
            x = int(round(cx + defecto["u_mm"] / px))
            esperado[max(0, int(cy - mitad)):int(cy + mitad), x:x + grosor] = True
        else:
            y = int(round(cy + defecto["v_mm"] / px))
            esperado[y:y + grosor, max(0, int(cx - mitad)):int(cx + mitad)] = True
        cambio = np.any(np.asarray(base) != np.asarray(con), axis=2)
        assert esperado.sum() > 100
        assert np.array_equal(cambio, esperado), f"el rayon cubre {int(cambio.sum())} px y deberia cubrir {int(esperado.sum())}"
        assert (np.asarray(con)[esperado] == defecto["valor"]).all()

    def test_el_desplazamiento_mueve_el_campo_y_la_verdad_lo_dice(self):
        a = GM.generar_arreglo(variante="L", dpi=DPI_PRUEBA)[1]
        b = GM.generar_arreglo(variante="L", dpi=DPI_PRUEBA, desplazamiento_px=(7.5, -3.25))[1]
        assert (b.centro_campo_px[0] - a.centro_campo_px[0], b.centro_campo_px[1] - a.centro_campo_px[1]) == pytest.approx((7.5, -3.25), abs=1e-9)
        assert b.marcas_px["UL"][0] - a.marcas_px["UL"][0] == pytest.approx(7.5, abs=1e-9)

    def test_la_fisica_del_anexo_no_cambio(self):
        """Con las dos extensiones apagadas es el generador calibrado del anexo (scripts/med_mensual_sintetica.py): sus numeros de control.
        (La igualdad bit a bit con el anexo la comprueba scripts/pf0_equivalencia_mensual.py, en el anexo.)"""
        c = GM.CALIB
        assert c["virgen_bgr"] == (82.0, 174.0, 105.5) and c["meseta_bgr"] == (39.0, 32.0, 1.0)
        assert c["k_bgr"] == (0.0, 0.7, 3.6) and c["sigma_mm"] == 2.3 and (c["s_cola"], c["lam_mm"]) == (0.04, 15.0)
        assert c["ruido"] == 1.5 and c["fondo_escaner"] == 250.0
        assert c["campo_rad_mm"] == (100.0, 99.0) and c["campo_luz_mm"] == (99.6, 99.8) and c["luz_desplazada_mm"] == (-0.6, 0.4)
        assert c["pelicula_mm"] == (115.0, 116.0) and c["campo_en_pelicula_mm"] == (57.3, 55.3)
        campo = GM.Campo()
        assert campo.wx0 == pytest.approx(99.7616543447782, abs=1e-9) and campo.wy == pytest.approx(98.7616543447782, abs=1e-9)
        assert campo.beta == 0.0 and campo.cupula_pct_40mm == 0.0
        assert float(campo.dosis(np.array(0.0), np.array(0.0))) == pytest.approx(1.0, abs=1e-12)
        assert float(campo.dosis(np.array(50.0), np.array(0.0))) == pytest.approx(0.5, abs=1e-9)         # el borde al 50 % esta a 50 mm
        assert float(campo.dosis(np.array(0.0), np.array(49.5))) == pytest.approx(0.5, abs=1e-9)
        assert float(campo.dosis(np.array(0.0), np.array(90.0))) == pytest.approx(0.04 * np.exp(-(90.0 - 98.7616543447782 / 2) / 15.0), rel=1e-6)   # la cola
        assert float(campo.respuesta_normalizada(np.array(0.5), "B")) == pytest.approx(0.5, abs=1e-12)
        assert float(campo.respuesta_normalizada(np.array(0.5), "R")) == pytest.approx((1 - np.exp(-1.8)) / (1 - np.exp(-3.6)), abs=1e-12)
        img = np.asarray(GM.generar_arreglo(dpi=DPI_PRUEBA, ruido=0, tinta=False)[0])
        h, w = img.shape[:2]
        centro = img[h // 2 - 2:h // 2 + 3, w // 2 - 2:w // 2 + 3].reshape(-1, 3).mean(axis=0)
        assert centro == pytest.approx(np.array([39.0, 32.0, 1.0]), abs=0.6)                         # la meseta: 39 / 32 / 1 (BGR)
        esquina = img[2:6, 2:6].reshape(-1, 3).mean(axis=0)
        assert esquina[0] > 70 and esquina[1] > 150 and esquina[2] > 90                               # la pelicula virgen (con la cola de dispersion: 82 / 174 / 105 menos algo)

    def test_la_cola_de_dispersion_decae_con_la_distancia_euclidiana_al_rectangulo_nominal(self):
        """La cola de dispersion es s * exp(-d / lam) con d la distancia al RECTANGULO nominal del campo (0 dentro). En las esquinas, fuera del campo en x Y en y, d es
        la distancia al VERTICE (euclidiana), no la mayor de las dos distancias a los lados (la de Chebyshev, que da una cola mas ancha: a 10 mm de las dos aristas, 10 mm en
        vez de 14.1). Se calcula d por fuerza bruta (el minimo de las distancias a puntos del borde del rectangulo, cada 0.0002 de su semiancho) y se compara con la que se
        lee de la dosis: -lam * ln(D / s), con la cupula apagada y la penumbra de las dos aristas despreciable (sondas a mas de 5 mm del rectangulo en x y en y)."""
        campo = GM.Campo()
        a, b = campo.wx0 / 2.0, campo.wy / 2.0
        t = np.arange(-1.0, 1.0 + 1e-9, 2e-4)
        borde = np.concatenate([np.stack([t * a, np.full_like(t, -b)], 1), np.stack([t * a, np.full_like(t, b)], 1),
                                np.stack([np.full_like(t, -a), t * b], 1), np.stack([np.full_like(t, a), t * b], 1)])
        lam, s = GM.CALIB["lam_mm"], GM.CALIB["s_cola"]
        sondas = [(a + 10.0, b + 10.0), (-(a + 14.0), b + 6.0), (a + 25.0, -(b + 7.0)), (-(a + 8.0), -(b + 30.0))]
        for u, v in sondas:
            d_fuerza_bruta = float(np.min(np.hypot(borde[:, 0] - u, borde[:, 1] - v)))
            d_chebyshev = max(abs(u) - a, abs(v) - b)
            assert min(abs(u) - a, abs(v) - b) > 5.0, "la sonda esta fuera del rectangulo nominal por mas de 5 mm en x Y en y: el producto de las dos penumbras (< 1e-9) no cuenta"
            assert d_fuerza_bruta - d_chebyshev > 0.5, "la sonda distingue la distancia euclidiana de la de Chebyshev (por lo menos 0.5 mm)"
            d_de_la_dosis = -lam * math.log(float(campo.dosis(np.array(u), np.array(v))) / s)
            assert d_de_la_dosis == pytest.approx(d_fuerza_bruta, abs=1e-6), f"sonda ({u:.1f}, {v:.1f}) mm"

    def test_las_extensiones_apagadas_dan_la_misma_verdad_que_el_anexo(self):
        v = GM.generar_arreglo(dpi=40)[1]
        assert v.exceso["L"] == pytest.approx(-0.4) and v.beta == 0.0 and v.cupula_pct_40mm == 0.0
        d1, _ = GM.mapa_dosis("A", 0.0, 60)
        d2, _ = GM.mapa_dosis("A", 0.0, 60, beta=0.0, cupula_pct_40mm=0.0)
        assert np.array_equal(d1, d2)


# ============================================================================================================================
# 4. EL GENERADOR DE BRAQUI: determinismo, la verdad contra la imagen y el modelo fisico
# ============================================================================================================================
def centro_x_de_la_mancha(img, verdad, canal=1, fondo=143.0, nivel=0.0, dosis=0.5):
    """x (px) del centro de la mancha en su fila central: punto medio de los dos cruces del contorno de `dosis` (0.5 = media altura: a mitad de camino
    entre el fondo y el nivel de la meseta) del perfil de la fila, interpolado entre las dos filas que rodean el centro verdadero. Integracion
    independiente: no usa ninguna funcion del generador. Con una franja de transito al 90 % de la dosis se pide `dosis` mayor que la franja (0.95)."""
    cy = verdad.centro_mancha_px[1]
    y0 = int(np.floor(cy))
    medio = fondo * (1.0 - dosis) + nivel * dosis
    centros = []
    for y in (y0, y0 + 1):
        fila = np.asarray(img)[y, :, canal].astype(float)
        idx = np.where(fila <= medio)[0]
        # solo el tramo contiguo mas largo (la mancha); la linea del marcador esta lejos de los bordes al 50 %
        cortes = np.where(np.diff(idx) > 1)[0]
        ini = np.r_[idx[0], idx[cortes + 1]]
        fin = np.r_[idx[cortes], idx[-1]]
        k = int(np.argmax(fin - ini))
        i, j = int(ini[k]), int(fin[k])
        a = (i - 1) + (medio - fila[i - 1]) / (fila[i] - fila[i - 1])
        b = j + (fila[j] - medio) / (fila[j] - fila[j + 1])
        centros.append((a + b) / 2.0)
    return centros[0] + (centros[1] - centros[0]) * (cy - y0)


def orientacion_del_eje_mayor(peso):
    """(angulo del eje mayor respecto de la horizontal en grados, en (-90, 90]; cociente de los autovalores) de una imagen de pesos, por momentos de
    segundo orden: integracion independiente de la orientacion de la mancha."""
    ys, xs = np.mgrid[0:peso.shape[0], 0:peso.shape[1]]
    w = peso.sum()
    mx, my = (peso * xs).sum() / w, (peso * ys).sum() / w
    cov = np.array([[(peso * (xs - mx) ** 2).sum(), (peso * (xs - mx) * (ys - my)).sum()],
                    [(peso * (xs - mx) * (ys - my)).sum(), (peso * (ys - my) ** 2).sum()]]) / w
    valores, vectores = np.linalg.eigh(cov)
    mayor = vectores[:, 1]
    angulo = np.degrees(np.arctan2(mayor[1], mayor[0]))
    if angulo > 90:
        angulo -= 180
    if angulo <= -90:
        angulo += 180
    return float(angulo), float(valores[1] / valores[0])


def _filas_oscuras(verde, medio):
    """(filas, anchos, centros) de las filas con algun pixel por debajo de `medio`: el ancho y el punto medio (px, con cruces interpolados) de su tramo oscuro contiguo mas largo.
    Integracion independiente del generador y del motor."""
    filas, anchos, centros = [], [], []
    for y in np.where((verde <= medio).any(axis=1))[0]:
        fila = verde[y]
        idx = np.where(fila <= medio)[0]
        cortes = np.where(np.diff(idx) > 1)[0]
        ini, fin = np.r_[idx[0], idx[cortes + 1]], np.r_[idx[cortes], idx[-1]]
        j = int(np.argmax(fin - ini))
        i0, i1 = int(ini[j]), int(fin[j])
        a = (i0 - 1) + (medio - fila[i0 - 1]) / (fila[i0] - fila[i0 - 1])
        b = i1 + (fila[i1] - medio) / (fila[i1] - fila[i1 + 1])
        filas.append(y)
        anchos.append(b - a)
        centros.append(0.5 * (a + b))
    return np.array(filas), np.array(anchos), np.array(centros)


def _verde_en_el_marco_del_motor(imagen, k):
    """El canal verde de una pagina que lleva la pelicula rotada `k` veces 90 grados antihorario (np.rot90), puesto en el MARCO DEL MOTOR: la imagen se gira el menor angulo que deja la
    linea VERTICAL (en (-90, 90] grados, antihorario en pantalla: es la convencion de `angulo_canonico` del motor y del cuaderno). Con k par la linea ya es vertical y no se gira; con k impar
    es horizontal y el menor giro son +90 grados (la parte de arriba pasa a la izquierda)."""
    verde = np.asarray(imagen)[:, :, 1].astype(float)
    return np.rot90(verde) if k % 2 else verde


def desfase_en_el_marco_del_motor(imagen, k, fondo=143.0):
    """Desfase (mm) que se MIDE en la imagen devuelta, en el marco del motor: linea (punto medio de las filas donde solo ella es oscura) menos punto medio de la mancha (las filas donde la
    region oscura es la mas ancha); positivo = la mancha a la izquierda de la linea. Para placas SIN banda de transito. No usa el generador ni el motor."""
    verde = _verde_en_el_marco_del_motor(imagen, k)
    _, anchos, centros = _filas_oscuras(verde, 0.5 * fondo)
    x_mancha = float(np.median(centros[anchos >= 0.8 * anchos.max()]))
    x_linea = float(np.median(centros[anchos <= 12.0]))
    return (x_linea - x_mancha) * GB.MM_POR_PX


def lado_de_la_banda_en_el_marco_del_motor(imagen, k, fondo=143.0):
    """+1 si la banda de transito (placa con `transito` > 0) queda a la DERECHA de la linea en el marco del motor, -1 si a la izquierda: la franja oscurece, entre 150 y 280 px de la
    linea y en las filas de la mancha, solo el lado donde esta."""
    verde = _verde_en_el_marco_del_motor(imagen, k)
    filas, anchos, centros = _filas_oscuras(verde, 0.5 * fondo)
    x_linea = int(round(float(np.median(centros[anchos <= 12.0]))))
    anchas = filas[anchos >= 20.0]
    y = int(round(0.5 * (anchas.min() + anchas.max())))
    oscuridad = lambda columnas: float(np.clip(fondo - verde[y - 1:y + 2, columnas], 0.0, None).mean())
    derecha, izquierda = oscuridad(slice(x_linea + 150, x_linea + 280)), oscuridad(slice(x_linea - 280, x_linea - 150))
    assert max(derecha, izquierda) > 20.0 * max(min(derecha, izquierda), 1.0), f"la banda no se ve de un solo lado ({derecha:.1f} a la derecha, {izquierda:.1f} a la izquierda)"
    return +1 if derecha > izquierda else -1


BRAQUI_BYTES = [("independiente", "png"), ("independiente", "jpeg"), ("fisico", "png"), ("fisico", "jpeg")]


class TestBraquiDeterminismo:
    @pytest.mark.parametrize("modelo,formato", BRAQUI_BYTES)
    def test_dos_llamadas_dan_los_mismos_bytes(self, modelo, formato):
        def hacer():
            if modelo == "independiente":
                return GB.generar_independiente(0.75, formato=formato, semilla=4)
            return GB.generar_fisico(0.75, formato=formato, semilla=4)
        a, b = hacer(), hacer()
        assert a.datos == b.datos and len(a.datos) > 5000
        assert a.clics == b.clics and a.verdad == b.verdad

    def test_la_semilla_cambia_el_ruido_y_el_fisico_sin_semilla_no_tiene_ruido(self):
        assert GB.generar_independiente(0.5, semilla=0).datos != GB.generar_independiente(0.5, semilla=1).datos
        assert GB.generar_fisico(0.5, semilla=1).datos != GB.generar_fisico(0.5, semilla=2).datos
        a, b = GB.generar_fisico(0.5), GB.generar_fisico(0.5, semilla=None)
        assert a.datos == b.datos
        liso = np.asarray(a.imagen)[600:660, 700:760, 1].astype(int)                 # pelicula lejos de la mancha: sin ruido solo la cola, que varia suavemente
        assert np.abs(np.diff(liso, axis=1)).max() <= 1 and np.abs(np.diff(liso, axis=0)).max() <= 1, "sin semilla la pelicula es lisa (sin ruido)"
        ruidoso = np.asarray(GB.generar_fisico(0.5, semilla=1).imagen)[600:660, 700:760, 1].astype(int)
        assert np.abs(np.diff(ruidoso, axis=1)).max() > 3

    def test_el_archivo_declara_600_dpi_y_es_del_formato_pedido(self):
        for formato, nombre in (("png", "PNG"), ("jpeg", "JPEG")):
            p = GB.generar_independiente(0.0, formato=formato)
            im = Image.open(io.BytesIO(p.datos))
            assert im.format == nombre and im.size == (1156, 672) and tuple(round(x) for x in im.info["dpi"]) == (600, 600)
            if formato == "jpeg":
                assert JpegImagePlugin.get_sampling(im) == 2 and im.quantization[0][0] == 2
        with pytest.raises(ValueError):
            GB.codificar(np.zeros((3, 3, 3), np.uint8), "tiff")

    def test_los_clics_estan_sobre_la_linea_en_las_filas_de_epson009(self):
        p = GB.generar_independiente(1.0, ruido=0)
        assert p.clics == [[300, 137], [300, 480]]
        assert [list(c) for c in p.verdad.clics] == p.clics
        img = np.asarray(p.imagen)
        for x, y in p.clics:
            assert img[y, x].max() <= 3, "el clic cae sobre la linea del marcador (tan oscura como la meseta)"
            assert img[y, x + 12].min() > 30, "y 12 px a un lado ya es pelicula"
        inclinada = GB.generar_independiente(0.0, ruido=0, inclinacion_deg=1.5)
        assert inclinada.clics != p.clics
        for x, y in inclinada.clics:
            assert np.asarray(inclinada.imagen)[y, x].max() <= 6


class TestBraquiElCentroDeLaManchaCoincideConLaVerdad:
    @pytest.mark.parametrize("kw", [{}, dict(dv_mancha_px=60.0), dict(ancho_mm=6.0, alto_mm=9.0, giro_elipse_deg=15.0),
                                    dict(ancho_mm=6.0, alto_mm=9.0, giro_elipse_deg=10.0, dv_mancha_px=60.0), dict(ancho_mm=4.5, alto_mm=4.5),
                                    dict(forma_mancha="rectangulo"), dict(sigma_borde_mm=1.2)],
                             ids=["principal", "corrida", "elipse15", "elipse10_corrida", "chica", "rectangulo", "borde_suave"])
    def test_el_centro_de_la_mancha_sin_ruido_medido_en_la_imagen_es_el_desfase_conocido(self, kw):
        errores = []
        for d in (-2.0, -1.25, -0.5, 0.0, 0.5, 1.25, 2.0):
            p = GB.generar_independiente(d, ruido=0, **kw)
            c = centro_x_de_la_mancha(p.imagen, p.verdad)
            desfase_medido = (p.verdad.x_linea - c) * GB.MM_POR_PX
            errores.append(desfase_medido - d)
            assert desfase_medido == pytest.approx(d, abs=0.02), f"desfase verdadero {d}"
        assert len(errores) == 7

    def test_desfase_positivo_es_la_mancha_a_la_izquierda_de_la_linea(self):
        izq = GB.generar_independiente(+1.5, ruido=0)
        der = GB.generar_independiente(-1.5, ruido=0)
        assert centro_x_de_la_mancha(izq.imagen, izq.verdad) < izq.verdad.x_linea
        assert centro_x_de_la_mancha(der.imagen, der.verdad) > der.verdad.x_linea
        assert izq.verdad.desfase_mm == 1.5 and izq.verdad.desfase_px == pytest.approx(1.5 / GB.MM_POR_PX)
        assert izq.verdad.centro_mancha_px[0] == pytest.approx(izq.verdad.x_linea - 1.5 / GB.MM_POR_PX, abs=1e-9)

    def test_la_mancha_corrida_no_esta_en_el_punto_medio_de_los_clics(self):
        p = GB.generar("independiente", "mancha_corrida", 0.0, ruido=0)
        y_clics = np.mean([c[1] for c in p.clics])
        assert p.verdad.centro_mancha_px[1] - y_clics == pytest.approx(60.0 + (GB.Y_CENTRO - y_clics), abs=1e-9)
        cy = p.verdad.centro_mancha_px[1]
        col = np.asarray(p.imagen)[:, int(p.verdad.x_linea) + 40, 1].astype(float)                 # una columna que cruza la mancha, fuera de la linea
        filas = np.where(col <= 71.5)[0]
        assert (filas.min() + filas.max()) / 2.0 == pytest.approx(cy, abs=1.0), "la mancha esta donde dice la verdad (en y)"

    def test_la_elipse_girada_tiene_el_eje_mayor_girado_lo_que_dice_el_modelo(self):
        for giro in (10.0, 15.0, 20.0):
            p = GB.generar("independiente", "elipse_girada", 0.0, ruido=0, giro_elipse_deg=giro, ancho_linea_px=-1.0)       # sin linea
            peso = (143.0 - np.asarray(p.imagen)[:, 100:600, 1].astype(float)) / 143.0
            angulo_con_la_horizontal, alargamiento = orientacion_del_eje_mayor(peso)
            angulo_con_la_vertical = angulo_con_la_horizontal - 90.0 if angulo_con_la_horizontal > 0 else angulo_con_la_horizontal + 90.0
            assert angulo_con_la_vertical == pytest.approx(giro, abs=0.5), (
                f"giro {giro}: la elipse gira en sentido horario en pantalla (como el giro de la pelicula mensual): su eje mayor, de 9 mm, "
                "se inclina hacia la izquierda al bajar")
            assert alargamiento > 1.8                                                              # 9 x 6 mm: la elipse es alargada

    def test_la_mancha_chica_mide_4_5_mm_entre_los_puntos_de_media_altura(self):
        p = GB.generar("independiente", "mancha_chica", 0.0, ruido=0)
        fila = np.asarray(p.imagen)[int(round(p.verdad.centro_mancha_px[1])), :, 1].astype(float)
        fila[int(p.verdad.x_linea) - 8:int(p.verdad.x_linea) + 9] = 143.0
        medio = 0.5 * 143.0
        idx = np.where(fila <= medio)[0]
        a = (idx[0] - 1) + (medio - fila[idx[0] - 1]) / (fila[idx[0]] - fila[idx[0] - 1])
        b = idx[-1] + (fila[idx[-1]] - medio) / (fila[idx[-1]] - fila[idx[-1] + 1])
        assert (b - a) * GB.MM_POR_PX == pytest.approx(4.5, abs=0.05)

    @pytest.mark.parametrize("sigma_mm", [0.6, 1.2])
    def test_el_borde_de_la_mancha_tiene_la_penumbra_del_modelo(self, sigma_mm):
        """El ancho 10-90 % del borde de una erf de sigma s mide 2.563 s (0.6 mm = 14.2 px da 36 px, como la sintetica calibrada del anexo)."""
        p = GB.generar_independiente(1.5, ruido=0, sigma_borde_mm=sigma_mm)
        fila = np.asarray(p.imagen)[int(round(p.verdad.centro_mancha_px[1])), :, 1].astype(float)
        izquierda = fila[:int(p.verdad.x_linea) - 20]                    # el borde izquierdo de la mancha, lejos de la linea
        def cruce(nivel):
            i = np.where(izquierda <= nivel)[0][0]
            return (i - 1) + (nivel - izquierda[i - 1]) / (izquierda[i] - izquierda[i - 1])
        ancho_px = cruce(0.1 * 143.0) - cruce(0.9 * 143.0)               # de 10 % de dosis (gris 0.9 * 143) a 90 % (gris 0.1 * 143)
        sigma_px = sigma_mm / GB.MM_POR_PX
        assert ancho_px == pytest.approx(2.5631 * sigma_px, abs=1.0)

    def test_la_pelicula_virgen_la_linea_y_la_banda_tienen_las_medidas_del_modelo(self):
        p = GB.generar_independiente(0.0, ruido=0)
        img = np.asarray(p.imagen)
        assert tuple(img[5, 5]) == (53, 143, 93) and tuple(img[660, 1150]) == (53, 143, 93), "la pelicula virgen de EPSON009 (BGR)"
        assert tuple(np.asarray(GB.generar_independiente(0.0, ruido=0, fondo=GB.FONDO_BRAQUI00).imagen)[5, 5]) == (53, 116, 47), "la de braqui_00"
        g = img[:, :, 1].astype(float)
        x0 = int(GB.X_LINEA)
        fila = g[400, x0 - 8:x0 + 9]
        a = np.where(fila <= 71.5)[0]
        ancho = (a[-1] + (fila[a[-1]] - 71.5) / (fila[a[-1]] - fila[a[-1] + 1])) - ((a[0] - 1) + (71.5 - fila[a[0] - 1]) / (fila[a[0]] - fila[a[0] - 1]))
        assert ancho == pytest.approx(7.0, abs=0.2), "la linea del marcador mide 7 px de ancho"
        filas = np.where(g[:, x0 + 1] <= 71.5)[0]
        assert (filas.min(), filas.max()) == (94, 523), "y 430 px de largo, centrada en la fila 308.5"
        q = GB.generar_independiente(0.0, ruido=0, transito=0.95, lado_transito=+1)
        cx, cy = q.verdad.centro_mancha_px
        perfil = np.asarray(q.imagen)[:, int(cx) + 250, 1].astype(float)
        fondo, minimo = 143.0, perfil.min()
        assert minimo == pytest.approx(143.0 * 0.05, abs=0.6), "la franja llega al 95 % de la dosis de la meseta"
        nivel = 0.5 * (fondo + minimo)
        idx = np.where(perfil <= nivel)[0]
        ancho_v = (idx[-1] + (perfil[idx[-1]] - nivel) / (perfil[idx[-1]] - perfil[idx[-1] + 1])) - ((idx[0] - 1) + (nivel - perfil[idx[0] - 1]) / (perfil[idx[0]] - perfil[idx[0] - 1]))
        assert ancho_v == pytest.approx(2.3548 * 0.6 / GB.MM_POR_PX, abs=2.0), "la franja es una gaussiana de sigma 0.6 mm en la direccion de la linea"
        assert abs((np.where(perfil <= nivel)[0].mean()) - cy) < 2.0

    def test_el_jitter_de_los_clics_los_mueve_a_los_lados_y_es_determinista(self):
        base = GB.generar_independiente(0.0, ruido=0)
        a = GB.generar_independiente(0.0, ruido=0, jitter_clic=1, semilla=3)
        b = GB.generar_independiente(0.0, ruido=0, jitter_clic=1, semilla=3)
        assert a.clics == b.clics and a.verdad.clics == b.verdad.clics
        assert [c[1] for c in a.clics] == [c[1] for c in base.clics], "el jitter es lateral"
        assert all(abs(x - bx) <= 1 for (x, _), (bx, _) in zip(a.clics, base.clics))
        movidos = {tuple(map(tuple, GB.generar_independiente(0.0, ruido=0, jitter_clic=1, semilla=s).clics)) for s in range(12)}
        assert len(movidos) > 1, "con semillas distintas los clics se mueven distinto"

    def test_las_variantes_devueltas_son_copias_y_no_se_pueden_corromper(self):
        a = GB.argumentos_de_la_variante("independiente", "mancha_corrida")
        a["dv_mancha_px"] = 1.0
        assert GB.argumentos_de_la_variante("independiente", "mancha_corrida") == {"dv_mancha_px": 60.0}

    def test_la_meseta_plana_en_JPEG_es_plana_en_1_como_braqui_00(self):
        p = GB.generar("independiente", "meseta_plana_jpeg", 0.5, ruido=0.15)
        assert p.formato == "jpeg"
        img = cv2.imdecode(np.frombuffer(p.datos, np.uint8), cv2.IMREAD_COLOR)
        cx, cy = (int(round(v)) for v in p.verdad.centro_mancha_px)
        nucleo = img[cy - 20:cy + 21, cx - 20:cx + 21, 1]
        sin_linea = nucleo[:, np.abs(np.arange(-20, 21) - (p.verdad.x_linea - cx)) > 8]
        assert (sin_linea == 1).mean() > 0.9, "casi toda la meseta vale exactamente 1 (braqui_00: el 99 %)"
        assert sin_linea.max() <= 2

    def test_el_transito_independiente_esta_del_lado_que_dice_la_verdad(self):
        for lado in (+1, -1):
            p = GB.generar_independiente(0.0, ruido=0, transito=0.95, lado_transito=lado)
            assert p.verdad.lado_transito == lado
            g = np.asarray(p.imagen)[:, :, 1].astype(float)
            cy = int(round(p.verdad.centro_mancha_px[1]))
            cx = int(round(p.verdad.centro_mancha_px[0]))
            derecha, izquierda = g[cy - 1:cy + 2, cx + 150:cx + 280].mean(), g[cy - 1:cy + 2, cx - 280:cx - 150].mean()
            con_franja, sin_franja = (derecha, izquierda) if lado > 0 else (izquierda, derecha)
            assert con_franja < 0.2 * sin_franja, f"la franja (95 % de la dosis de la meseta) oscurece solo el lado {lado}"
        sin = GB.generar_independiente(0.0, ruido=0)
        assert sin.verdad.lado_transito is None and sin.verdad.sentido_fisico is None

    def test_el_sentido_fisico_es_antes_si_la_mancha_esta_del_lado_del_cable(self):
        assert GB.sentido_fisico_de(-0.36, +1) == "antes de la marca"          # braqui_00: -0.362 mm con el cable a la derecha
        assert GB.sentido_fisico_de(+0.36, +1) == "despues de la marca"
        assert GB.sentido_fisico_de(-0.36, -1) == "despues de la marca"
        assert GB.sentido_fisico_de(+0.36, -1) == "antes de la marca"
        assert GB.sentido_fisico_de(0.0, +1) == "en la marca"
        assert GB.sentido_fisico_de(0.7, None) is None
        p = GB.generar_independiente(-1.0, ruido=0, transito=0.9, lado_transito=+1)
        assert p.verdad.sentido_fisico == "antes de la marca"
        assert centro_x_de_la_mancha(p.imagen, p.verdad, dosis=0.95) > p.verdad.x_linea, "'antes' = la mancha del lado del cable (aqui la derecha)"
        q = GB.generar_independiente(+1.0, ruido=0, transito=0.9, lado_transito=+1)
        assert q.verdad.sentido_fisico == "despues de la marca"

    def test_el_sentido_fisico_solo_es_en_la_marca_si_el_desfase_es_exactamente_cero(self):
        """La verdad es un desfase CONOCIDO, no medido: 0.03 mm (o 0.001 mm) esta de un lado de la marca y se dice. 'En la marca' es solo el cero exacto; un umbral (por ejemplo, el
        0.05 mm de una tolerancia de medida) borraria el sentido justo en los desfases chicos que B.2 mide con la mayor exigencia."""
        for lado in (+1, -1):
            for pequeno in (0.03, 0.001, 1e-9):
                assert GB.sentido_fisico_de(+pequeno, lado) == ("despues de la marca" if lado > 0 else "antes de la marca"), (pequeno, lado)
                assert GB.sentido_fisico_de(-pequeno, lado) == ("antes de la marca" if lado > 0 else "despues de la marca"), (pequeno, lado)
            assert GB.sentido_fisico_de(0.0, lado) == "en la marca"
        p = GB.generar_independiente(0.03, ruido=0, transito=0.95, lado_transito=+1)
        assert p.verdad.sentido_fisico == "despues de la marca"

    @pytest.mark.parametrize("lado", [+1, -1])
    def test_la_banda_de_transito_independiente_es_observable_del_lado_que_dice_la_verdad(self, lado):
        """La verdad dice 'antes' o 'despues de la marca' segun de que lado de la mancha esta la banda de transito, y eso solo sirve si ESA banda se puede ver: el motor (y el cuaderno)
        la miran entre 12 y 50 mm del centro de la mancha, en las filas del cateter frente a la pelicula de arriba y de abajo. Se mide con el contraste independiente de la banda
        (`GB.contraste_de_transito`, la misma definicion): con la banda a la izquierda y la linea en x = 300 solo habia 12.7 mm de pelicula a ese lado y el contraste era 0, de modo que el
        sentido de la verdad no se podia reproducir. Con `lado_transito` = -1 la escena es la espejada (como `cable_izquierda`): la linea queda en ancho - 1 - 300.37."""
        for d in (-1.0, 0.0, 1.0):
            p = GB.generar_independiente(d, ruido=0, transito=0.95, lado_transito=lado)
            img = np.asarray(p.imagen).astype(float)
            assert GB.contraste_de_transito(img, lado) > 60.0, f"la banda de {'la derecha' if lado > 0 else 'la izquierda'} no se ve (d = {d:+.1f}): contraste {GB.contraste_de_transito(img, lado):.1f}"
            assert GB.contraste_de_transito(img, -lado) < 5.0, "y del otro lado no hay banda"
            assert p.verdad.x_linea == pytest.approx(GB.X_LINEA if lado > 0 else GB.FORMA[1] - 1 - GB.X_LINEA)
        sin_banda = GB.generar_independiente(0.5, ruido=0)
        assert sin_banda.verdad.x_linea == GB.X_LINEA, "sin banda de transito la linea queda donde siempre"

    def test_la_posicion_de_la_linea_se_puede_pedir_aunque_haya_banda_a_la_izquierda(self):
        """El valor por omision de `x_linea` con la banda a la izquierda es el espejado, pero un llamador puede pedir la linea donde quiera (y asumir que a la izquierda hay poca pelicula)."""
        p = GB.generar_independiente(0.0, ruido=0, transito=0.95, lado_transito=-1, x_linea=GB.X_LINEA)
        assert p.verdad.x_linea == GB.X_LINEA
        assert [c[0] for c in p.clics] == [300, 300]
        q = GB.generar_independiente(0.0, ruido=0, transito=0.95, lado_transito=-1, x_linea=700.0)
        assert q.verdad.x_linea == 700.0 and [c[0] for c in q.clics] == [700, 700]

    @pytest.mark.parametrize("inclinacion", [-1.5, 1.5, 3.0])
    def test_el_centro_declarado_con_la_linea_inclinada_es_el_de_la_mancha_de_la_imagen_independiente(self, inclinacion):
        """Con la linea inclinada (y la mancha corrida a lo largo de ella) el centro que declara la verdad es el centroide de la dosis de la imagen sin la linea: 2.5 px de error si el
        signo del giro de `uc` o de `dv` se invirtiera (a 1.5 grados y 2 mm)."""
        for d, dv in ((2.0, 0.0), (-2.0, 60.0)):
            p = GB.generar_independiente(d, ruido=0, inclinacion_deg=inclinacion, dv_mancha_px=dv, ancho_linea_px=-1.0)          # sin la linea
            peso = (143.0 - np.asarray(p.imagen)[:, :, 1].astype(float)) / 143.0
            ys, xs = np.mgrid[0:peso.shape[0], 0:peso.shape[1]]
            centroide = ((peso * xs).sum() / peso.sum(), (peso * ys).sum() / peso.sum())
            assert centroide == pytest.approx(p.verdad.centro_mancha_px, abs=0.05), f"inclinacion {inclinacion}, desfase {d}, dv {dv}"


# sesgo (mm) del punto medio aparente de la region saturada respecto del centro GEOMETRICO de la fuente, sin ruido (medido el 12-10-2026 con
# punto_medio_aparente_mm): fisica de la anisotropia y del transito, no error de ninguna medida. (minimo, maximo) con margen.
SESGO_FISICO_MM = {
    "control": (-0.03, 0.03), "principal": (-0.03, 0.03), "solo_anisotropia": (0.005, 0.045), "solo_transito": (-0.05, -0.005),
    "anisotropia_simetrica": (-0.03, 0.03), "cable_estrecho": (-0.10, -0.04), "transito_x5": (-0.12, -0.065), "clics_descentrados": (-0.03, 0.03),
    "plana1": (-0.03, 0.03), "cable_izquierda": (-0.03, 0.03), "transito_x5_izquierda": (0.065, 0.12), "cateter_oblicuo_3": (-0.03, 0.01),
    "cateter_oblicuo_15": (0.0, 0.05),
}


class TestBraquiElModeloFisico:
    def test_la_tabla_de_calibracion_cubre_todos_los_escenarios_y_solo_esos(self):
        assert set(GB.CALIBRACION_FISICA) == set(GB.ESCENARIOS)
        for nombre, c in GB.CALIBRACION_FISICA.items():
            assert set(c) == {"A", "T_tr"} and c["A"] > 0 and c["T_tr"] >= 0
            assert (c["T_tr"] > 0) == GB.ESCENARIOS[nombre].get("transito", True), f"{nombre}: el transito se calibra si y solo si el escenario lo lleva"
        assert len(GB.ESCENARIOS) >= 22

    @pytest.mark.parametrize("escenario", sorted(GB.ESCENARIOS))
    def test_la_cuerda_de_saturacion_sin_ruido_es_la_calibrada(self, escenario):
        """La mancha de cada escenario mide la cuerda de saturacion que le toca: la objetivo del escenario en la escala del motor menos el desfase de la
        medida independiente (OFFSET_CUERDA_MM; el motor mide a saltos de un pixel, 0.04 mm, y 0.11-0.21 mm de mas en los 19 escenarios del anexo)."""
        par = GB.parametros_del_escenario(escenario)
        cal = GB.CALIBRACION_FISICA[escenario]
        GF, NT = GB.componentes_dosis(par, 0.0)
        img = GB.escanear(cal["A"] * GF + cal["T_tr"] * NT, par, con_linea=False, cuantizar=False)
        cuerda = GB.cuerda_de_saturacion_mm(img)
        assert cuerda + GB.OFFSET_CUERDA_MM == pytest.approx(par["cuerda_mm"], abs=0.12), escenario

    @pytest.mark.parametrize("escenario", [e for e in sorted(GB.ESCENARIOS) if GB.ESCENARIOS[e].get("transito", True)])
    def test_el_contraste_de_la_banda_de_transito_es_el_calibrado(self, escenario):
        par = GB.parametros_del_escenario(escenario)
        cal = GB.CALIBRACION_FISICA[escenario]
        GF, NT = GB.componentes_dosis(par, 0.0)
        img = GB.escanear(cal["A"] * GF + cal["T_tr"] * NT, par, cuantizar=False)
        contraste = GB.contraste_de_transito(img, +1)
        esperado = 43.0 if par["factor_transito"] == 5.0 else GB.CONTRASTE_OBJETIVO
        assert contraste == pytest.approx(esperado, abs=3.0 if par["factor_transito"] == 5.0 else 1.2), escenario

    @pytest.mark.parametrize("escenario,cuerda,contraste", [("control", 6.2411, None), ("principal", 6.2658, 12.283), ("cable_estrecho", 6.2666, 12.562),
                                                            ("transito_x5", 6.2379, 42.641), ("mancha_chica", 4.4076, 12.836), ("mancha_grande", 8.2581, 12.477),
                                                            ("plana1", 6.25, 12.7), ("cateter_oblicuo_15", 6.25, None), ("clics_descentrados", 6.2653, 12.862)])
    def test_los_valores_de_control_de_la_medida_independiente_no_se_mueven(self, escenario, cuerda, contraste):
        """Fija estrechos (0.01 mm, 0.1 niveles) los numeros que la medida independiente da hoy para escenarios clave: la tabla de calibracion no deriva en silencio
        (la tolerancia de las pruebas anteriores, 0.12 mm, absorbe el desfase de la medida del motor; esta no)."""
        par = GB.parametros_del_escenario(escenario)
        cal = GB.CALIBRACION_FISICA[escenario]
        GF, NT = GB.componentes_dosis(par, 0.0)
        assert GB.cuerda_de_saturacion_mm(GB.escanear(cal["A"] * GF + cal["T_tr"] * NT, par, con_linea=False, cuantizar=False)) == pytest.approx(cuerda, abs=0.01)
        if contraste is not None:
            assert GB.contraste_de_transito(GB.escanear(cal["A"] * GF + cal["T_tr"] * NT, par, cuantizar=False), +1) == pytest.approx(contraste, abs=0.1)

    def test_el_grano_de_la_pelicula_se_agrega_con_la_semilla_y_es_determinista(self):
        con = np.asarray(GB.generar_fisico(0.0, escenario="grano_pelicula", semilla=5, ruido=0).imagen).astype(int)
        sin = np.asarray(GB.generar_fisico(0.0, escenario="grano_pelicula", semilla=5, ruido=0, grano_sigma=0.0).imagen).astype(int)
        repetido = np.asarray(GB.generar_fisico(0.0, escenario="grano_pelicula", semilla=5, ruido=0).imagen).astype(int)
        assert np.array_equal(con, repetido)
        assert (con != sin).any(axis=2).sum() > 500, "el grano cambia la imagen en la penumbra de la mancha"
        assert not np.array_equal(con, np.asarray(GB.generar_fisico(0.0, escenario="grano_pelicula", semilla=6, ruido=0).imagen).astype(int))

    def test_sin_transito_no_hay_banda(self):
        par = GB.parametros_del_escenario("control")
        GF, NT = GB.componentes_dosis(par, 0.0)
        img = GB.escanear(GB.CALIBRACION_FISICA["control"]["A"] * GF, par, cuantizar=False)
        assert abs(GB.contraste_de_transito(img, +1)) < 0.5

    @pytest.mark.parametrize("escenario", sorted(SESGO_FISICO_MM))
    def test_el_punto_medio_aparente_esta_dentro_del_sesgo_fisico_documentado(self, escenario):
        """La verdad del modelo fisico es el centro GEOMETRICO de la fuente; el punto medio de la region saturada se corre unas decimas de mm por la
        anisotropia y el transito (B.2: -0.10 / -0.08 mm con el transito x 5 o la caida estrecha del cable). Pendiente 1.00 +- 0.01."""
        minimo, maximo = SESGO_FISICO_MM[escenario]
        desfases, sesgos = [], []
        for d in (-2.0, -1.0, 0.0, 1.0, 2.0):
            p = GB.generar_fisico(d, escenario=escenario)
            aparente = GB.punto_medio_aparente_mm(np.asarray(p.imagen).astype(float), x_linea=p.verdad.x_linea)
            desfases.append(d)
            sesgos.append(aparente - d)
        assert minimo <= float(np.mean(sesgos)) <= maximo, f"{escenario}: sesgo medio {np.mean(sesgos):+.4f}"
        pendiente = np.polyfit(desfases, [s + d for s, d in zip(sesgos, desfases)], 1)[0]
        assert pendiente == pytest.approx(1.0, abs=0.01)

    @pytest.mark.parametrize("escenario", ["principal", "inclinada", "cable_izquierda", "clics_descentrados"])
    def test_los_clics_del_modelo_fisico_estan_sobre_la_linea_del_marcador(self, escenario):
        """Los dos clics enteros caen sobre la linea (tan oscura como la meseta), tambien con la linea inclinada 1.5 grados y con la imagen invertida."""
        p = GB.generar_fisico(0.0, escenario=escenario)
        img = np.asarray(p.imagen)
        assert len(p.clics) == 2 and p.clics[0][1] < p.clics[1][1]
        for x, y in p.clics:
            assert img[y, x].max() <= 6, f"{escenario}: el clic ({x}, {y}) no cae sobre la linea del marcador"
        if escenario == "inclinada":
            assert p.clics[0][0] != p.clics[1][0], "la linea inclinada 1.5 grados desplaza los clics en x"
            assert p.verdad.inclinacion_deg == 1.5

    def test_generar_fisico_usa_la_calibracion_que_se_le_pasa(self):
        """`calibracion` (A, T_tr) pisa la del escenario: pasar la misma da los mismos bytes que no pasar nada; con la escala de dosis A 1.5 veces mayor la region saturada es mas ancha
        (de 6.23 a 7.35 mm); con T_tr = 0 no hay banda de transito (contraste 12 niveles con la calibrada, 0 sin ella)."""
        c = GB.CALIBRACION_FISICA["principal"]
        por_omision = GB.generar_fisico(0.0)
        assert GB.generar_fisico(0.0, calibracion=dict(c)).datos == por_omision.datos
        imagen = lambda p: np.asarray(p.imagen).astype(float)
        mas_dosis = GB.generar_fisico(0.0, calibracion={"A": 1.5 * c["A"], "T_tr": c["T_tr"]})
        assert GB.cuerda_de_saturacion_mm(imagen(mas_dosis)) > GB.cuerda_de_saturacion_mm(imagen(por_omision)) + 0.8
        sin_banda = GB.generar_fisico(0.0, calibracion={"A": c["A"], "T_tr": 0.0})
        assert GB.contraste_de_transito(imagen(por_omision), +1) > 8.0 and GB.contraste_de_transito(imagen(sin_banda), +1) < 1.0
        assert sin_banda.datos != por_omision.datos

    def test_el_centro_declarado_con_la_linea_inclinada_es_el_de_la_mancha_de_la_imagen_fisica(self):
        """El escenario `inclinada` (linea a 1.5 grados): el centro que declara la verdad esta donde esta la region saturada de la imagen SIN la linea (medida con las cuerdas de
        saturacion, independiente de la formula de la verdad), a 0.6 px; el signo del giro corre ese centro 2.5 px en y con un desfase de 2 mm."""
        par = GB.parametros_del_escenario("inclinada")
        cal = GB.CALIBRACION_FISICA["inclinada"]
        for d in (-2.0, 2.0):
            p = GB.generar_fisico(d, escenario="inclinada")
            GF, NT = GB.componentes_dosis(par, d)
            gris = GB.gris_de(GB.escanear(cal["A"] * GF + cal["T_tr"] * NT, par, con_linea=False, cuantizar=False))
            y, cuerda, xi, xd = GB.cuerdas_de_saturacion_px(gris)
            elegidas = cuerda >= 0.8 * cuerda.max()
            medido = (float(np.median((xi[elegidas] + xd[elegidas]) / 2.0)), float((y[elegidas].min() + y[elegidas].max()) / 2.0))
            assert medido == pytest.approx(p.verdad.centro_mancha_px, abs=0.6), f"desfase {d}"

    def test_la_meseta_plana_del_modelo_fisico_vale_1_en_JPEG_como_braqui_00(self):
        p = GB.generar("fisico", "meseta_plana_jpeg", 0.0)
        assert p.formato == "jpeg" and p.verdad.parametros["piso_escaner"] == 1.0 and p.verdad.parametros["ruido"] == 0.15
        img = cv2.imdecode(np.frombuffer(p.datos, np.uint8), cv2.IMREAD_COLOR)
        cx, cy = (int(round(v)) for v in p.verdad.centro_mancha_px)
        nucleo = img[cy - 8:cy + 9, cx - 8:cx + 9, :]
        assert (nucleo == 1).mean() > 0.9, "la meseta del modelo fisico con el piso del escaner en 1 es plana en 1 (braqui_00: el 99 % de los pixeles vale 1)"
        sin_piso = np.asarray(GB.generar_fisico(0.0, escenario="principal").imagen)[cy - 8:cy + 9, cx - 8:cx + 9, :]
        assert (sin_piso == 0).mean() > 0.5, "sin ese piso la meseta se recorta a 0"

    def test_el_cable_a_la_izquierda_es_la_imagen_invertida_del_cable_a_la_derecha(self):
        for d in (-1.0, 0.5):
            der = GB.generar_fisico(d, escenario="principal")
            izq = GB.generar_fisico(-d, escenario="cable_izquierda")
            assert np.array_equal(np.asarray(izq.imagen), np.asarray(der.imagen)[:, ::-1])
            assert izq.verdad.lado_transito == -1 and der.verdad.lado_transito == +1
            assert izq.verdad.x_linea == pytest.approx(1156 - 1 - der.verdad.x_linea)
            assert izq.clics == [[1156 - 1 - x, y] for x, y in der.clics]
            assert izq.verdad.sentido_fisico == der.verdad.sentido_fisico, "el mismo hecho fisico visto en el espejo"
            assert izq.verdad.desfase_mm == -der.verdad.desfase_mm

    def test_el_transito_esta_del_lado_del_cable(self):
        for escenario, lado in (("principal", +1), ("cable_izquierda", -1), ("transito_x5", +1), ("transito_x5_izquierda", -1)):
            p = GB.generar_fisico(0.0, escenario=escenario)
            assert p.verdad.lado_transito == lado
            g = GB.gris_de(np.asarray(p.imagen).astype(float))
            cy, cx = int(round(p.verdad.centro_mancha_px[1])), int(round(p.verdad.centro_mancha_px[0]))
            columnas = slice(cx + 330, cx + 700) if lado > 0 else slice(cx - 700, cx - 330)
            banda = g[cy - 2:cy + 3, columnas].mean()                        # las filas del cateter, a 14-30 mm de la mancha del lado del cable
            pelicula = g[cy - 150:cy - 120, columnas].mean()                 # la pelicula de arriba, a la misma distancia
            assert banda < pelicula - 5, f"{escenario}: la banda es mas oscura que la pelicula de al lado, del lado {lado}"

    def test_la_calibracion_independiente_reproduce_la_del_anexo(self):
        """`calibrar` (medida independiente, sin el motor) llega a las mismas constantes que el anexo calibro con el motor: A a ~1 % y T_tr a ~5 %."""
        for escenario, tol_t in (("control", None), ("principal", 0.06)):
            c = GB.calibrar(GB.parametros_del_escenario(escenario))
            t = GB.CALIBRACION_FISICA[escenario]
            assert c["A"] == pytest.approx(t["A"], rel=0.02), escenario
            if tol_t is not None:
                assert c["T_tr"] == pytest.approx(t["T_tr"], rel=tol_t), escenario

    def test_las_calibraciones_nuevas_de_PF0_son_las_que_da_calibrar(self):
        for escenario in ("cateter_oblicuo_15",):
            c = GB.calibrar(GB.parametros_del_escenario(escenario))
            t = GB.CALIBRACION_FISICA[escenario]
            assert c["A"] == pytest.approx(t["A"], rel=1e-6) and c["T_tr"] == pytest.approx(t["T_tr"], abs=1e-9)

    def test_los_cambios_que_obligan_a_recalibrar_se_rechazan(self):
        with pytest.raises(ValueError):
            GB.generar_fisico(0.0, F0=0.5)
        with pytest.raises(ValueError):
            GB.generar_fisico(0.0, cuerda_mm=5.0)
        GB.generar_fisico(0.0, ruido=0.5, semilla=1)                       # estos si: no mueven la calibracion
        with pytest.raises(KeyError):
            GB.parametros_del_escenario("no_existe")
        with pytest.raises(ValueError, match="obligan a recalibrar"):                  # `lado_cable` tampoco se cambia sin definir un escenario: esta guarda salta ANTES que la de la linea inclinada
            GB.generar_fisico(0.0, escenario="inclinada", lado_cable=-1)

    def test_el_modelo_fisico_con_ruido_y_semilla_tiene_la_sigma_pedida(self):
        con = np.asarray(GB.generar_fisico(0.0, semilla=3).imagen).astype(float)
        sin = np.asarray(GB.generar_fisico(0.0).imagen).astype(float)
        residuo = (con - sin)[:60, :200, :].ravel()
        assert 1.3 < residuo.std() < 1.7


class TestBraquiLasVariantesDificilesDeB2:
    def test_las_variantes_dificiles_llevan_los_numeros_de_B2(self):
        """Mancha a 60 px del punto medio de los clics; meseta plana en 1 en JPEG; franja al 90-97 % del tope de un solo lado; elipse 6 x 9 mm girada 10-20
        grados; mancha de 4.5 mm; pagina entera. En el modelo fisico: la fuente a 2.5 mm de los clics, la banda x 5 del cable, el cateter oblicuo."""
        ind = lambda v: GB.argumentos_de_la_variante("independiente", v)
        assert ind("mancha_corrida") == {"dv_mancha_px": 60.0}
        plana = ind("meseta_plana_jpeg")
        assert plana["formato"] == "jpeg" and plana["nivel_meseta"] == 1.0 and plana["nivel_linea"] == 1.0 and plana["ruido"] == 0.15
        banda = ind("transito_un_lado")
        assert 0.90 <= banda["transito"] <= 0.97 and banda["lado_transito"] in (+1, -1)
        elipse = ind("elipse_girada")
        assert (elipse["ancho_mm"], elipse["alto_mm"]) == (6.0, 9.0) and 10.0 <= elipse["giro_elipse_deg"] <= 20.0
        assert ind("mancha_chica") == {"ancho_mm": 4.5, "alto_mm": 4.5}
        assert ind("pagina_entera") == {"pagina": True}
        fis = lambda v: GB.argumentos_de_la_variante("fisico", v)
        assert fis("mancha_corrida")["escenario"] == "clics_descentrados" and GB.ESCENARIOS["clics_descentrados"] == {"dv_mm": 2.5}
        assert fis("mancha_chica")["escenario"] == "mancha_chica" and GB.ESCENARIOS["mancha_chica"] == {"cuerda_mm": 4.5}
        assert fis("transito_un_lado")["escenario"] == "transito_x5" and GB.ESCENARIOS["transito_x5"] == {"factor_transito": 5.0}
        assert fis("elipse_girada")["escenario"] == "cateter_oblicuo_15" and GB.ESCENARIOS["cateter_oblicuo_15"]["alfa_deg"] == 15.0
        assert fis("meseta_plana_jpeg")["formato"] == "jpeg" and GB.ESCENARIOS[fis("meseta_plana_jpeg")["escenario"]] == {"piso_escaner": 1.0, "ruido": 0.15}
        assert fis("pagina_entera") == {"escenario": "principal", "pagina": True}

    def test_las_variantes_son_las_seis_de_B2(self):
        assert GB.VARIANTES_DIFICILES == ("mancha_corrida", "meseta_plana_jpeg", "transito_un_lado", "elipse_girada", "mancha_chica", "pagina_entera")
        for modelo in ("independiente", "fisico"):
            for variante in GB.VARIANTES_DIFICILES:
                assert GB.argumentos_de_la_variante(modelo, variante)
        with pytest.raises(KeyError):
            GB.argumentos_de_la_variante("fisico", "no_existe")

    @pytest.mark.parametrize("modelo", ["independiente", "fisico"])
    @pytest.mark.parametrize("variante", [v for v in GB.VARIANTES_DIFICILES if v != "pagina_entera"])
    def test_cada_variante_se_genera_y_dice_su_verdad(self, modelo, variante):
        p = GB.generar(modelo, variante, 0.5)
        assert p.verdad.modelo == modelo and p.verdad.desfase_mm == 0.5
        assert p.imagen.shape == (672, 1156, 3)
        assert len(p.clics) == 2 and p.verdad.pagina is None
        if variante == "meseta_plana_jpeg":
            assert p.formato == "jpeg"
        else:
            assert p.formato == "png"
        con_banda = variante == "transito_un_lado" if modelo == "independiente" else variante != "elipse_girada"
        assert p.verdad.sentido_fisico == ("despues de la marca" if con_banda else None), (modelo, variante)    # desfase +0.5 = del lado de la punta, con el cable a la derecha

    def test_la_mancha_corrida_del_modelo_fisico_esta_a_2_5_mm_de_los_clics(self):
        p = GB.generar("fisico", "mancha_corrida", 0.0)
        y_clics = np.mean([c[1] for c in p.clics])
        assert (p.verdad.centro_mancha_px[1] - GB.Y_CENTRO) * GB.MM_POR_PX == pytest.approx(2.5, abs=1e-9)
        assert p.verdad.parametros["escenario"] == "clics_descentrados" and p.verdad.parametros["dv_mm"] == 2.5
        assert y_clics == pytest.approx(GB.Y_CENTRO, abs=1.0)

    def test_la_mancha_chica_fisica_mide_4_5_mm_de_cuerda(self):
        par = GB.parametros_del_escenario("mancha_chica")
        assert par["cuerda_mm"] == 4.5
        grande = GB.parametros_del_escenario("mancha_grande")
        assert grande["cuerda_mm"] == 8.5

    @pytest.mark.parametrize("escenario,alfa", [("control", 0.0), ("cateter_oblicuo_3", 3.0), ("cateter_oblicuo_15", 15.0)])
    def test_el_cateter_oblicuo_inclina_el_eje_mayor_de_la_mancha_fisica(self, escenario, alfa):
        """Sobre la mancha sin la linea del marcador (que le quita un pedazo y sesga los momentos): su eje mayor sigue al cateter, `alfa_deg` en sentido
        horario respecto de la normal a la linea. Es el analogo fisico de la elipse girada del generador independiente."""
        par = GB.parametros_del_escenario(escenario)
        cal = GB.CALIBRACION_FISICA[escenario]
        GF, NT = GB.componentes_dosis(par, 0.0)
        g = GB.gris_de(GB.escanear(cal["A"] * GF + cal["T_tr"] * NT, par, con_linea=False, cuantizar=False))
        angulo, alargamiento = orientacion_del_eje_mayor(np.clip(40.0 - g[:, 100:600], 0.0, None))      # la region saturada y su entorno inmediato
        assert par["alfa_deg"] == alfa
        assert angulo == pytest.approx(alfa, abs=0.5)
        assert alargamiento > 1.0
        p = GB.generar("fisico", "elipse_girada", 0.0)
        assert p.verdad.sentido_fisico is None, "este escenario no lleva banda de transito (a 15 grados se aleja de las filas de la mancha)"

    @pytest.mark.parametrize("modelo", ["independiente", "fisico"])
    def test_la_pagina_entera_trae_la_misma_escena_en_medio_del_blanco_del_escaner(self, modelo):
        base = GB.generar_independiente(0.75, semilla=3) if modelo == "independiente" else GB.generar_fisico(0.75, semilla=3)
        pag = GB.generar_independiente(0.75, semilla=3, pagina=True) if modelo == "independiente" else GB.generar_fisico(0.75, semilla=3, pagina=True)
        assert pag.imagen.shape == (6600, 5100, 3)
        x0, y0 = pag.verdad.pagina["origen"]
        assert pag.verdad.pagina == {"origen": ((5100 - 1156) // 2, (6600 - 672) // 2), "forma": (6600, 5100), "rotar_k90": 0}
        assert np.array_equal(np.asarray(pag.imagen)[y0:y0 + 672, x0:x0 + 1156], np.asarray(base.imagen))
        fuera = np.ones(pag.imagen.shape[:2], bool)
        fuera[y0:y0 + 672, x0:x0 + 1156] = False
        assert (np.asarray(pag.imagen)[fuera] == 250).all(), "fuera de la pelicula es el blanco del escaner"
        assert pag.clics == [[x + x0, y + y0] for x, y in base.clics]
        assert pag.verdad.centro_mancha_px == pytest.approx((base.verdad.centro_mancha_px[0] + x0, base.verdad.centro_mancha_px[1] + y0))
        assert pag.verdad.desfase_mm == base.verdad.desfase_mm and pag.verdad.sentido_fisico == base.verdad.sentido_fisico

    @pytest.mark.parametrize("k", [0, 1, 2, 3])
    def test_rotar_la_pagina_lleva_los_clics_a_donde_estan_en_la_pagina_rotada(self, k, monkeypatch):
        monkeypatch.setattr(GB, "PAGINA_PX", (1500, 1900))
        for generar in (lambda: GB.generar_independiente(0.5, ruido=0, pagina=True, rotar_k90=k, origen_pagina=(300, 400)),
                        lambda: GB.generar_fisico(0.5, pagina=True, rotar_k90=k, origen_pagina=(300, 400))):
            p = generar()
            esperado = (1500, 1900, 3) if k % 2 == 0 else (1900, 1500, 3)
            assert p.imagen.shape == esperado
            img = np.asarray(p.imagen)
            for x, y in p.clics:
                assert img[y, x].max() <= 6, f"k={k}: el clic ({x},{y}) no cae sobre la linea del marcador"
            # la linea es vertical con k par y horizontal con k impar: 12 px al lado del clic, en la direccion perpendicular, ya es pelicula
            (x, y) = p.clics[0]
            lado = img[y, x + 12] if k % 2 == 0 else img[y + 12, x]
            assert lado.min() > 25
            assert p.verdad.pagina["rotar_k90"] == k
            assert (p.verdad.centro_mancha_px is None) == (k != 0)

    @pytest.mark.parametrize("k", [0, 1, 2, 3])
    @pytest.mark.parametrize("modelo", ["independiente", "fisico"])
    def test_el_desfase_de_la_verdad_de_la_pagina_rotada_es_el_que_se_mide_en_la_imagen_devuelta(self, modelo, k, monkeypatch):
        """La verdad describe la imagen DEVUELTA, no la escena antes de rotarla (lo que dicen los docstrings): con la pagina rotada 180 grados la mancha que estaba a la izquierda de la linea
        queda a la derecha y el desfase de la verdad cambia de signo; con la linea horizontal (k impar) 'a la izquierda' es el lado que el menor giro que la deja vertical (+90 grados
        antihorario, la convencion del motor) lleva a la izquierda: ARRIBA de la linea. Se MIDE en los pixeles de la pagina devuelta, sin pasar por el generador ni por el motor
        (el motor lee +0.99, -0.99, -0.99, +0.99 mm para k = 0..3 con un desfase real de +1.0). El SENTIDO FISICO (antes o despues de la marca) es un hecho de la pelicula y no cambia al rotarla."""
        monkeypatch.setattr(GB, "PAGINA_PX", (1500, 1900))
        signo = (+1, -1, -1, +1)[k]
        for d in (+1.25, -0.75):
            if modelo == "independiente":
                p = GB.generar_independiente(d, ruido=0, pagina=True, rotar_k90=k, origen_pagina=(300, 400))
            else:
                p = GB.generar_fisico(d, pagina=True, rotar_k90=k, origen_pagina=(300, 400))
            medido = desfase_en_el_marco_del_motor(p.imagen, k)
            assert medido == pytest.approx(p.verdad.desfase_mm, abs=0.03 if modelo == "independiente" else 0.12), f"{modelo}, k={k}, desfase {d}: la imagen devuelta dice {medido:+.3f}"
            assert p.verdad.desfase_mm == d * signo
            assert p.verdad.desfase_px == pytest.approx(d * signo / GB.MM_POR_PX)
            lado = None if modelo == "independiente" else +1                                      # el cable del modelo fisico principal esta a la derecha de la escena
            assert p.verdad.sentido_fisico == GB.sentido_fisico_de(d, lado), "el sentido fisico es el de la escena: rotar la pagina no lo cambia"
            assert p.verdad.lado_transito == (None if lado is None else lado * signo)
            assert p.verdad.sentido_fisico == GB.sentido_fisico_de(p.verdad.desfase_mm, p.verdad.lado_transito), "la verdad es coherente consigo misma: su desfase y su lado dicen su sentido"

    @pytest.mark.parametrize("k", [0, 1, 2, 3])
    @pytest.mark.parametrize("lado", [+1, -1])
    def test_el_lado_de_la_banda_de_la_verdad_de_la_pagina_rotada_es_el_que_se_ve_en_la_imagen_devuelta(self, lado, k, monkeypatch):
        """El lado de la banda de transito de la verdad tambien es el de la imagen devuelta, en el marco del motor (el que el motor llama 'derecha' o 'izquierda'); medido por la oscuridad de la
        franja a cada lado de la linea. Se lo compara con el sentido fisico, que es el mismo antes y despues de rotar."""
        monkeypatch.setattr(GB, "PAGINA_PX", (1500, 1900))
        signo = (+1, -1, -1, +1)[k]
        p = GB.generar_independiente(0.5, ruido=0, transito=0.95, lado_transito=lado, pagina=True, rotar_k90=k, origen_pagina=(300, 400))
        assert lado_de_la_banda_en_el_marco_del_motor(p.imagen, k) == p.verdad.lado_transito == lado * signo
        assert p.verdad.sentido_fisico == GB.sentido_fisico_de(0.5, lado)
        assert p.verdad.sentido_fisico == GB.sentido_fisico_de(p.verdad.desfase_mm, p.verdad.lado_transito)

    @pytest.mark.parametrize("k", [0, 1, 2, 3])
    def test_la_transformacion_de_la_pagina_lleva_cada_pixel_a_donde_va(self, k):
        """Tres pixeles marcados de la escena: tras ubicarla en la pagina (origen) y rotarla k veces 90 grados antihorario, cada uno esta donde dicen las
        coordenadas transformadas (y solo ahi)."""
        escena = np.zeros((40, 70, 3), np.uint8)
        escena[5, 10] = (11, 0, 0)
        escena[30, 60] = (22, 0, 0)
        escena[0, 0] = (33, 0, 0)
        pagina, pts = GB._en_pagina(escena, [[10, 5], [60, 30], [0, 0]], (20, 15), (100, 120), k)
        assert pagina.shape == ((100, 120, 3) if k % 2 == 0 else (120, 100, 3))
        for (x, y), valor in zip(pts, (11, 22, 33)):
            assert pagina[y, x, 0] == valor
            assert (pagina[:, :, 0] == valor).sum() == 1
        assert (pagina[:, :, 0] == 250).sum() == pagina.shape[0] * pagina.shape[1] - 40 * 70, "fuera de la pelicula es blanco del escaner"
        assert pagina.dtype == np.uint8

    def test_la_pelicula_no_cabe_en_una_pagina_mas_chica_que_ella(self, monkeypatch):
        monkeypatch.setattr(GB, "PAGINA_PX", (500, 500))
        with pytest.raises(ValueError, match="no cabe"):
            GB.generar_independiente(0.0, pagina=True)


class TestLasGuardasDeLosGeneradores:
    """Cada linea de los modulos auxiliares que ninguna prueba ejecutaba (medido con `sys.settrace` sobre los dos archivos de PF.0, anexo `logs/PF0/correccion_ronda1/lineas_sin_ejecutar.py`)
    es una pieza que ninguna prueba puede proteger (la clase del hallazgo X3: un parametro sin ejercer): las guardas que rechazan lo que no tiene sentido y las ramas de las medidas
    independientes que solo se alcanzan con un caso limite."""

    def test_generar_fisico_rechaza_un_lado_de_cable_que_no_es_mas_ni_menos_uno(self, monkeypatch):
        monkeypatch.setitem(GB.ESCENARIOS, "cable_cero", {"lado_cable": 0})
        monkeypatch.setitem(GB.CALIBRACION_FISICA, "cable_cero", dict(GB.CALIBRACION_FISICA["principal"]))
        with pytest.raises(ValueError, match=r"lado_cable: \+1"):
            GB.generar_fisico(0.0, escenario="cable_cero")

    def test_el_cable_a_la_izquierda_no_se_combina_con_la_linea_inclinada(self, monkeypatch):
        monkeypatch.setitem(GB.ESCENARIOS, "izquierda_inclinada", {"lado_cable": -1, "phi_deg": 1.5})
        monkeypatch.setitem(GB.CALIBRACION_FISICA, "izquierda_inclinada", dict(GB.CALIBRACION_FISICA["principal"]))
        with pytest.raises(ValueError, match="no se combina con la linea inclinada"):
            GB.generar_fisico(0.0, escenario="izquierda_inclinada")

    def test_un_escenario_sin_calibrar_se_calibra_en_el_acto_y_los_tabulados_no(self, monkeypatch):
        llamadas = []
        monkeypatch.setitem(GB.ESCENARIOS, "recien_llegado", {"ruido": 1.0})
        monkeypatch.setattr(GB, "calibrar", lambda par: llamadas.append(par) or {"A": 6.0, "T_tr": 0.03})
        assert GB.calibracion_del_escenario("recien_llegado") == {"A": 6.0, "T_tr": 0.03}
        assert llamadas == [GB.parametros_del_escenario("recien_llegado")]
        assert GB.calibracion_del_escenario("principal") is GB.CALIBRACION_FISICA["principal"] and len(llamadas) == 1, "un escenario tabulado no se recalibra"

    def test_calibrar_con_un_factor_de_transito_vuelve_a_ajustar_la_escala_de_dosis_en_un_intervalo_acotado(self, monkeypatch):
        """`calibrar` ajusta por rondas la escala de dosis A (la cuerda de saturacion) y la del transito T_tr (el contraste de la banda), 4 rondas con transito. Con `factor_transito` != 1 (el
        escenario `transito_x5`) multiplica T_tr por el factor y RECALIBRA A en un intervalo de 0.3 a 3 veces la A ya ajustada (la banda x 5 suma dosis a la mancha; con A muy bajo la 'meseta' pasaria a ser
        la banda y la cuerda dejaria de ser monotona en A). Con el factor en 1 no hay recalibracion. Se prueba el flujo con una biseccion falsa (calibrar de verdad cuesta decenas de segundos)."""
        llamadas = []
        respuestas = iter([2.0, 0.01] * 4 + [3.0])

        def falsa(f, lo, hi, objetivo, iteraciones, log=True):
            llamadas.append((lo, hi, objetivo, iteraciones))
            return next(respuestas)
        monkeypatch.setattr(GB, "_biseccion", falsa)
        par = GB.parametros_del_escenario("transito_x5")
        assert par["factor_transito"] == 5.0 and par["transito"]
        assert GB.calibrar(par) == {"A": 3.0, "T_tr": pytest.approx(0.01 * 5.0)}
        assert len(llamadas) == 9
        assert llamadas[-1] == (0.3 * 2.0, 3.0 * 2.0, par["cuerda_mm"] - GB.OFFSET_CUERDA_MM, 26)
        llamadas.clear()
        respuestas = iter([2.0, 0.01] * 4)
        assert GB.calibrar(GB.parametros_del_escenario("principal")) == {"A": 2.0, "T_tr": 0.01}, "con el factor en 1 no hay recalibracion"
        assert len(llamadas) == 8

    def test_las_medidas_independientes_ignoran_las_cuerdas_cortadas_por_el_borde_y_dan_cero_sin_mancha(self):
        gris = np.full((6, 40), 140.0)
        gris[2, 0:10] = 0.0                      # una cuerda que toca el borde izquierdo: no se mide (su extremo no existe)
        gris[3, 10:20] = 0.0                     # una completa
        gris[4, 30:40] = 0.0                     # otra que toca el borde derecho
        y, cuerda, xi, xd = GB.cuerdas_de_saturacion_px(gris)
        assert list(y) == [3]
        assert cuerda[0] == pytest.approx((19 + 2.5 / 140.0) - (9 + 137.5 / 140.0), abs=1e-9)
        sin_mancha = np.full((6, 40, 3), 140.0)
        assert len(GB.cuerdas_de_saturacion_px(GB.gris_de(sin_mancha))[0]) == 0
        assert GB.cuerda_de_saturacion_mm(sin_mancha) == 0.0
        assert GB.contraste_de_transito(sin_mancha, +1) == 0.0, "sin region saturada no hay banda que medir"

    def test_el_campo_mensual_avisa_cuando_no_hay_cruce_del_50_por_ciento(self):
        """Una fila a 80 mm del centro (en la cola de dispersion, fuera del campo) no tiene borde al 50 %: la verdad lo dice con un error, no con un numero sin sentido."""
        with pytest.raises(ValueError, match="no hay cruce del 50"):
            GM.Campo().borde_fila(80.0, +1)


# ============================================================================================================================
# 5. INDEPENDENCIA DEL MOTOR
# ============================================================================================================================
PAQUETES_DE_LA_APLICACION = {"analisisImagenes", "services", "data", "ui", "models", "utils", "main", "mcc_PTW_read", "scripts", "build_exe"}
PERMITIDOS = {"io", "math", "dataclasses", "numpy", "scipy", "cv2", "PIL", "tifffile"}


def _importaciones(ruta):
    arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"))
    modulos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            modulos.append(("." * nodo.level) + (nodo.module or ""))
    return modulos


@pytest.mark.parametrize("modulo", ["_placa_mensual_sintetica.py", "_placa_braqui_sintetica.py"])
def test_los_generadores_son_independientes_del_motor(modulo):
    """Paso 13 del protocolo del plan: la sintetica de la suite es un generador INDEPENDIENTE del motor. Si importara algo de la aplicacion (y en
    particular `analisisImagenes.posicion_inicial_braqui`) la verdad podria heredar los errores del motor que valida."""
    importados = _importaciones(TESTS / modulo)
    assert len(importados) >= 4, "el recorrido de importaciones no es vacio"
    raices = {m.split(".")[0] for m in importados}
    assert not raices & PAQUETES_DE_LA_APLICACION, f"{modulo} importa codigo de la aplicacion: {sorted(raices & PAQUETES_DE_LA_APLICACION)}"
    assert not any(m.startswith(".") for m in importados), "ni importaciones relativas"
    assert raices <= PERMITIDOS, f"{modulo}: importa fuera de lo previsto {sorted(raices - PERMITIDOS)}"
    texto = (TESTS / modulo).read_text(encoding="utf-8")
    assert "posicion_inicial_braqui" not in "\n".join(l for l in texto.splitlines() if l.lstrip().startswith(("import ", "from ")))


def test_el_censo_de_importaciones_ve_una_importacion_prohibida(tmp_path):
    """El tripwire de arriba no es ciego: sobre un archivo que importa el motor, lo ve."""
    malo = tmp_path / "malo.py"
    malo.write_text("import numpy\nfrom analisisImagenes import posicion_inicial_braqui\nimport services.respaldo\n", encoding="utf-8")
    raices = {m.split(".")[0] for m in _importaciones(malo)}
    assert raices & PAQUETES_DE_LA_APLICACION == {"analisisImagenes", "services"}


def test_los_modulos_auxiliares_no_se_coleccionan_como_pruebas():
    assert not GM.__name__.startswith("test_") and not GB.__name__.startswith("test_")
