"""PD.2 (PLAN_PELICULA_DIARIA_BRAQUI_13-11.md, revisada el 22-11): la película diaria de braquiterapia se mide con la resolución REAL de la imagen (la declarada si la regla de la tira
la confirma; si no, la única candidata, 200, 300 o 600 ppp, que la confirme; si ninguna, «no medible» con su motivo), con el número de paradas que tenga la tira (una parada es una
línea con su mancha a menos de medio paso; lo que no se mide se dice y queda fuera de los promedios) y en la capa VERDE, que la figura y el informe declaran.
La verdad la da un generador independiente del motor (`tira`): N paradas cada 10 mm a la resolución dada, cada una con su mancha gaussiana en la verde y una línea fina.
Rojo contra ee3b857: caen las que piden la resolución real, las paradas variables y la capa verde; pasan las de 600 declarados que la base ya medía bien."""
import ast
import gc
import html
import os
import re
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image
from PyQt5.QtWidgets import QMessageBox

import analisisImagenes.Analisis_PlacaRC as rc

RAIZ = Path(__file__).resolve().parent.parent
FONDO, MANCHA, LINEA = 205.0, 70.0, 35.0
VERDAD_DESPLAZAMIENTOS_MM = (0.1, 0.2, 0.3)
NADA_GUARDADO = ("", None, None, "", None, None)


def tira(dpi, n=11, paso_mm=10.0, margen_mm=7.0, tenue=(), faltan=(), extra_sin_mancha_mm=None, doble_mm=None, recorte_mm=0.0, senal="G", posiciones_mm=None, corrida_mm=None):
    """RGB uint8 de una tira: N paradas cada `paso_mm` a `dpi` píxeles por pulgada; cada parada, una línea oscura de 0.3 mm y su mancha gaussiana (sigma 1.6 mm) corrida 0.1, 0.2 o 0.3 mm.
    `senal` dice qué capa lleva la tira ("G", "B" o "GB"); las demás quedan planas. La roja está recortada en el piso (3 niveles), como en las tiras reales.
    `posiciones_mm` pone las líneas donde se diga (desde el margen) y `corrida_mm` corre la mancha de una parada {índice: mm}."""
    px_mm = dpi / 25.4
    posiciones_mm = list(posiciones_mm) if posiciones_mm is not None else [i * paso_mm for i in range(n)]
    n = len(posiciones_mm)
    ancho = int(round((2 * margen_mm + posiciones_mm[-1]) * px_mm))
    alto = int(round(12.0 * px_mm))
    x = np.arange(ancho, dtype=float)
    perfil = np.full(ancho, FONDO)
    lineas = [(margen_mm + p) * px_mm for p in posiciones_mm]
    for i, xl in enumerate(lineas):
        if i in faltan:
            continue
        a = MANCHA * (0.3 if i in tenue else 1.0)
        corrida = (corrida_mm or {}).get(i, VERDAD_DESPLAZAMIENTOS_MM[i % 3])
        perfil -= a * np.exp(-0.5 * ((x - (xl + corrida * px_mm)) / (1.6 * px_mm)) ** 2)
    capa = np.repeat(perfil[None, :], alto, axis=0)
    finas = [(xl, LINEA) for xl in lineas]
    if extra_sin_mancha_mm is not None:
        finas.append((lineas[-1] + extra_sin_mancha_mm * px_mm, LINEA))
    if doble_mm is not None:  # un rayón más claro que la línea
        finas.append((lineas[2] + doble_mm * px_mm, 110.0))
    medio = max(2, int(round(0.3 * px_mm)))
    for xl, nivel in finas:
        c = int(round(xl))
        if c + medio < ancho:
            capa[:, c - medio // 2:c - medio // 2 + medio] = nivel
    capa = capa + ((np.arange(alto)[:, None] * 7 + np.arange(ancho)[None, :] * 3) % 5 - 2) * 0.8
    plana = np.full_like(capa, FONDO)
    g = capa if "G" in senal else plana
    b = capa - 70 if "B" in senal else plana - 70
    img = np.stack([np.full_like(capa, 3.0), g, b], axis=2)
    if recorte_mm:
        img = img[:, int(round(recorte_mm * px_mm)):]
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


def guardar(ruta, rgb, dpi=None, formato="TIFF"):
    Image.fromarray(rgb).save(ruta, format=formato, **({} if dpi is None else {"dpi": (dpi, dpi)}))
    return str(ruta)


def analizar(ruta, canvas=None, filtro="verde"):
    return rc.analizar_lineas(ruta, metodo=True, umbral_relativo=1.0, distancia_minima=40, mostrar=canvas is not None, filtro=filtro, canvas=canvas)


def texto(informe):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", informe)))


def lista(informe, rotulo):
    m = re.search(re.escape(rotulo) + r"</b> <span style='font-weight:normal'>\[([^\]]*)\]", informe)
    return [float(v) for v in m.group(1).split(",")] if m else []


def distancias(informe):
    return lista(informe, "Distancias entre líneas(mm):")


def desplazamientos(informe):
    return lista(informe, "Desplazamientos entre líneas y centros circulares (mm):")


def paradas(informe):
    m = re.search(r"Paradas en la tira:</b> <span style='font-weight:normal'>(\d+)</span>", informe)
    return int(m.group(1)) if m else None


def aviso(informe):
    m = re.match(re.escape("<b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;RESULTADO DE ANÁLISIS DE LA IMAGEN</b>") + r"<br>(.*?)<br>", informe)
    return m.group(1) if m and not m.group(1).startswith("<b>") else ""


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    """Un diálogo modal bajo offscreen cuelga el proceso: aquí hace caer la prueba."""
    def modal(*args, **kwargs):
        raise AssertionError(f"se abrió un diálogo modal: {args[1:3]}")
    for tipo in ("information", "critical", "warning", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(modal))


@pytest.fixture(scope="module")
def d(tmp_path_factory):
    return tmp_path_factory.mktemp("pd2")


def midio_bien(informe, n):
    """Mide la tira: n paradas, n - 1 distancias de 10 mm y desplazamientos de décimas de milímetro."""
    dist, des = distancias(informe), desplazamientos(informe)
    assert paradas(informe) == n, texto(informe)
    assert len(dist) == n - 1 and abs(np.mean(dist) - 10.0) <= 0.1 and max(abs(np.array(dist) - 10.0)) <= 0.4, dist
    assert len(des) == n and max(des) < 0.8 and abs(np.mean(des) - 0.2) <= 0.3, des


# ================================================================================================================ la resolución real

class TestLaResolucionReal:
    @pytest.mark.parametrize("dpi", [200, 300, 600])
    def test_la_declarada_que_la_tira_confirma_se_usa(self, d, dpi):
        informe = analizar(guardar(d / f"declarada_{dpi}.tif", tira(dpi), dpi))
        midio_bien(informe, 11)
        if dpi == 600:
            assert aviso(informe) == "", "con los 600 del procedimiento confirmados no hay aviso, como hoy"
        else:
            assert "la regla de la tira confirma la declarada" in aviso(informe), aviso(informe)

    @pytest.mark.parametrize("dpi, n", [(400, 8), (1200, 6)])
    def test_una_declarada_que_no_es_candidata_se_usa_si_la_tira_la_confirma(self, d, dpi, n):
        """PD2-D2: la declarada va primero aunque no sea de las candidatas (200, 300, 600): con 400 o 1200 ppp y las líneas cada 10 mm, la regla de la tira la confirma y se mide con ella."""
        informe = analizar(guardar(d / f"no_candidata_{dpi}.tif", tira(dpi, n=n), dpi))
        midio_bien(informe, n)
        assert f"resolución declarada {dpi} dpi" in aviso(informe) and "la regla de la tira confirma la declarada y se mide con ella" in aviso(informe), aviso(informe)

    @pytest.mark.parametrize("real", [200, 300, 600])
    def test_un_recorte_de_editor_a_96_se_mide_con_la_resolucion_que_confirma_la_tira(self, d, real):
        informe = analizar(guardar(d / f"editor_{real}.tif", tira(real, n=10), 96.012))
        midio_bien(informe, 10)
        a = aviso(informe)
        assert "lo que escribe un editor" in a and f"confirma {real} dpi, la resolución real" in a, a

    def test_sin_resolucion_declarada_se_mide_con_la_que_confirma_la_tira(self, d):
        informe = analizar(guardar(d / "sin_dato.png", tira(200, n=9), None, "PNG"))
        midio_bien(informe, 9)
        assert "no declara su resolución" in aviso(informe) and "confirma 200 dpi" in aviso(informe)

    @pytest.mark.parametrize("declarada, real", [(300, 600), (600, 300), (200, 600)])
    def test_una_declarada_distinta_de_la_real_se_corrige_con_la_tira_y_se_dice(self, d, declarada, real):
        informe = analizar(guardar(d / f"d{declarada}_r{real}.tif", tira(real), declarada))
        midio_bien(informe, 11)
        a = aviso(informe)
        assert f"resolución declarada {declarada} dpi" in a and f"confirma {real} dpi, la resolución real" in a, a

    @pytest.mark.parametrize("declarada", [600, 200, None])
    def test_una_tira_que_no_cuadra_con_ninguna_resolucion_no_da_milimetros(self, d, declarada):
        """Líneas cada 7 mm: con 600 salen a 7, con 300 a 14 y con 200 a 21; ninguna cumple la regla de 10 mm ±10 %: la escala no se inventa, ni siquiera con 600 declarados."""
        informe = analizar(guardar(d / f"siete_{declarada}.png", tira(600, paso_mm=7.0), declarada, "PNG"))
        assert distancias(informe) == [] and desplazamientos(informe) == [] and paradas(informe) is None
        assert "ninguna resolución candidata" in aviso(informe) and "sin una resolución confirmada no hay milímetros ni medidas" in aviso(informe), aviso(informe)
        assert (declarada is None) != ("la regla de la tira no confirma la declarada" in aviso(informe)), aviso(informe)

    def test_con_pocas_lineas_y_una_resolucion_que_no_es_la_del_procedimiento_no_hay_milimetros(self, d):
        informe = analizar(guardar(d / "tres_200.tif", tira(200, n=3), 200))
        assert distancias(informe) == [] and "no hay líneas suficientes" in aviso(informe), texto(informe)

    @pytest.mark.parametrize("n", [2, 3])
    def test_con_pocas_lineas_y_600_declarados_se_mide_a_600_sin_comprobar(self, d, n):
        informe = analizar(guardar(d / f"pocas_{n}_600.tif", tira(600, n=n), 600))
        assert aviso(informe) == "" and paradas(informe) == n and len(distancias(informe)) == n - 1, texto(informe)

    def test_sin_distancias_la_escala_no_se_inventa(self, d):
        ruta = guardar(d / "otra.tif", tira(300), 300)
        assert rc.metadata(ruta)[0] is None and rc.metadata(ruta, np.array([118.1, 118.1]))[0] is None
        assert rc.metadata(ruta, np.full(10, 118.11))[0] == pytest.approx(25.4 / 300 / 10)

    def test_la_mitad_de_las_distancias_debe_cumplir_la_regla_y_no_solo_la_mediana(self, d):
        """Distancias erráticas cuya mediana cae en 10 mm por azar no confirman nada (como el registro 88 de la base de producción); tres en regla de diez tampoco."""
        ruta = guardar(d / "errat.tif", tira(200), 200)
        erraticas = np.array([42.5, 6.6, 10.0, 13.4, 6.7]) * 300 / 25.4      # con 300: la mediana, 10 mm; en regla, 1 de 5
        assert rc.metadata(ruta, erraticas)[0] is None
        px = 200 / 25.4
        assert rc.metadata(ruta, np.array([10.0] * 4 + [25.0] * 6) * px)[0] is None, "4 de 10 en regla no son la mitad"
        assert rc.metadata(ruta, np.array([10.0, 10.0, 10.0, 25.0, 31.0]) * px)[0] == pytest.approx(25.4 / 200 / 10)

    @pytest.mark.parametrize("n, en_regla, confirma", [(6, 3, True), (7, 3, False), (8, 4, True), (9, 4, False), (10, 5, True)])
    def test_la_mitad_exacta_de_las_distancias_en_regla_confirma_y_una_menos_no(self, d, n, en_regla, confirma):
        """«La mitad o más» (PD2-D1): 3 de 6, 4 de 8 y 5 de 10 confirman; 3 de 7 y 4 de 9, que no llegan a la mitad, no."""
        distancias_px = np.array([10.0] * en_regla + [25.0] * (n - en_regla)) * 200 / 25.4
        assert (rc.metadata(guardar(d / "mitad.tif", tira(200, n=3), 200), distancias_px)[0] is not None) == confirma

    @pytest.mark.parametrize("mm, confirma", [((10.0, 10.0, 15.0), False), ((10.0, 10.0, 10.0), True), ((10.0, 10.0, 15.0, 10.0), True), ((10.0, 10.0, 15.0, 16.0), False)])
    def test_hacen_falta_tres_distancias_en_regla_aunque_sean_la_mitad_o_mas(self, d, mm, confirma):
        """PD2-D1 pide al menos 3 distancias en regla Y la mitad o más: 2 de 3 son más de la mitad y no bastan, y 2 de 4 son la mitad justa y tampoco; 3 de 3 y 3 de 4 sí."""
        ruta = guardar(d / "tres_en_regla.tif", tira(300, n=3), 300)
        assert (rc.metadata(ruta, np.array(mm) * 300 / 25.4)[0] is not None) == confirma

    def test_dos_candidatas_que_cuadran_dan_una_resolucion_ambigua(self, d, monkeypatch):
        monkeypatch.setitem(rc.REGLA_DE_LA_TIRA, "resoluciones_candidatas_dpi", [300.0, 310.0])
        ruta = guardar(d / "ambigua.png", tira(300), None, "PNG")
        escala, a = rc.metadata(ruta, np.full(10, 10 * 305 / 25.4))
        assert escala is None and "las líneas cuadran con 300 y 310 dpi: la resolución es ambigua" in a, a

    def test_las_candidatas_son_las_resoluciones_usadas(self):
        assert rc.REGLA_DE_LA_TIRA == {"paso_mm": 10.0, "tolerancia_relativa": 0.10, "distancias_minimas": 3, "resoluciones_candidatas_dpi": [200.0, 300.0, 600.0]}

    @pytest.mark.parametrize("nombre, rgb, dpi, formato, esperado", [
        ("aviso_editor", (300, 10), 96.012, "TIFF", "TIFF, 8 bits por canal, {ancho} × 142 px. el archivo declara 96.01 dpi, lo que escribe un editor al guardar un recorte. con 300 dpi, 9 de las 9 "
                                                    "distancias entre líneas salen a 10 mm ±10 % (la mediana, {mediana} mm): la regla de la tira confirma 300 dpi, la resolución real, y se mide con ella."),
        ("aviso_otra", (200, 11), 200, "TIFF", "TIFF, 8 bits por canal, {ancho} × 94 px. resolución declarada 200 dpi. con 200 dpi, 10 de las 10 distancias entre líneas salen a 10 mm ±10 % "
                                              "(la mediana, {mediana} mm): la regla de la tira confirma la declarada y se mide con ella."),
        ("aviso_pocas", (200, 3), 200, "TIFF", "TIFF, 8 bits por canal, {ancho} × 94 px. resolución declarada 200 dpi. no hay líneas suficientes para decidir la resolución con la regla de la tira "
                                               "(líneas cada 10 mm): hacen falta 3 distancias entre líneas y hay 2. sin una resolución confirmada no hay milímetros ni medidas."),
        ("aviso_ninguna", (600, 11), 600, "PNG", "PNG, 8 bits por canal, {ancho} × 283 px. resolución declarada 600 dpi. con 600 dpi, 0 de las 10 distancias entre líneas salen a 10 mm ±10 % "
                                                "(la mediana, {mediana} mm): la regla de la tira no confirma la declarada. ninguna resolución candidata (200, 300, 600 dpi) cumple la regla de la tira. "
                                                "sin una resolución confirmada no hay milímetros ni medidas.")])
    def test_el_aviso_dice_lo_que_declara_el_archivo_y_lo_que_decide_la_regla(self, d, nombre, rgb, dpi, formato, esperado):
        """El texto completo, con la cifra que lo respalda; la mediana es la de las distancias que la regla ve."""
        real, n = rgb
        imagen = tira(real, n=n, paso_mm=7.0 if nombre == "aviso_ninguna" else 10.0)
        a = aviso(analizar(guardar(d / f"{nombre}.{formato.lower()}", imagen, dpi, formato)))
        m = re.search(r"la mediana, (\d+\.\d\d) mm", a)
        assert a == esperado.format(ancho=imagen.shape[1], mediana=m.group(1) if m else ""), a


# ================================================================================================================ las paradas que tenga la tira

class TestLasParadasQueTengaLaTira:
    @pytest.mark.parametrize("n", [4, 7, 15])
    def test_una_tira_de_n_paradas_se_mide_con_n(self, d, n):
        midio_bien(analizar(guardar(d / f"n{n}.tif", tira(300, n=n), 300)), n)

    @pytest.mark.parametrize("como", ["tenue", "faltan"])
    def test_una_mancha_tenue_o_que_falta_es_no_medible_y_no_entra_en_los_promedios(self, d, como):
        informe = analizar(guardar(d / f"{como}.tif", tira(600, **{como: (5,)}), 600))
        t = texto(informe)
        assert paradas(informe) == 10 and t.count("no es una parada") == 1 and t.count("falta una parada medible") == 1, t
        assert informe.count("&nbsp;&nbsp;&nbsp;&nbsp;<span style='font-weight:normal'>No medible, fuera de los promedios: ") == 2 and "una parada medible entre ellas</span><br>" in informe
        assert re.search(r"entre las paradas 5 y 6 hay (19|20)\.\d\d mm: falta una parada medible entre ellas", t), t
        assert re.search(r"el pico en 5[67]\.\d mm no tiene mancha a menos de 5 mm: no es una parada", t), t
        assert len(distancias(informe)) == 8 and abs(np.mean(distancias(informe)) - 10.0) <= 0.1, "la distancia de 20 mm no entra en el promedio"
        assert max(desplazamientos(informe)) < 0.8, "cada línea va con su mancha, no con la siguiente"

    def test_una_tira_recortada_se_mide_con_las_paradas_que_tiene(self, d):
        midio_bien(analizar(guardar(d / "recorte.tif", tira(600, recorte_mm=4.0), 600)), 11)

    def test_una_linea_sin_mancha_despues_de_la_ultima_parada_no_es_una_parada(self, d):
        informe = analizar(guardar(d / "extra.tif", tira(600, extra_sin_mancha_mm=6.3, margen_mm=12.0), 600))
        midio_bien(informe, 11)
        assert "no tiene mancha a menos de 5 mm: no es una parada" in texto(informe)

    @pytest.mark.parametrize("a_mm", [2.0, 4.0])
    def test_un_rayon_a_menos_de_medio_paso_de_una_linea_no_es_otra_parada(self, d, a_mm):
        midio_bien(analizar(guardar(d / f"doble_{a_mm}.tif", tira(600, doble_mm=a_mm), 600)), 11)

    def test_las_distancias_de_hasta_1_5_pasos_cuentan_y_las_de_mas_no(self, d):
        """Una distancia de 14 mm entra (es la medida que el control vigila); una de 17 mm deja una parada sin medir entre las dos y no entra."""
        informe = analizar(guardar(d / "irregular.tif", tira(600, posiciones_mm=[0, 10, 20, 30, 44, 54, 64, 81, 91, 101]), 600))
        dist, t = distancias(informe), texto(informe)
        assert paradas(informe) == 10 and len(dist) == 8 and any(abs(x - 14.0) <= 0.2 for x in dist) and not any(x > 15 for x in dist), dist
        assert re.search(r"entre las paradas 7 y 8 hay 1[67]\.\d\d mm: falta una parada medible entre ellas", t), t

    @pytest.mark.parametrize("hueco_mm, entra", [(14.4, True), (15.6, False)])
    def test_el_corte_de_1_5_pasos_deja_pasar_14_4_mm_y_no_15_6_mm(self, d, hueco_mm, entra):
        """El corte está en 1.5 pasos (15 mm): una distancia de 14.4 mm entra en los promedios; una de 15.6 mm no, y el informe dice que falta una parada medible entre las dos.
        (Los picos caen en píxeles enteros sobre la banda de la línea: la distancia medida difiere de la puesta hasta 0.2 mm.)"""
        informe = analizar(guardar(d / f"hueco_{hueco_mm}.tif", tira(600, posiciones_mm=[0, 10, 20, 30, 30 + hueco_mm, 40 + hueco_mm, 50 + hueco_mm, 60 + hueco_mm]), 600))
        dist, t = distancias(informe), texto(informe)
        assert paradas(informe) == 8, t
        assert any(14.0 <= x <= 15.0 for x in dist) == entra and not any(x > 15.0 for x in dist), dist
        assert bool(re.search(r"entre las paradas 4 y 5 hay 1[45]\.\d\d mm: falta una parada medible entre ellas", t)) == (not entra), t

    def test_una_mancha_a_4_mm_de_su_linea_se_mide_y_no_se_descarta(self, d):
        informe = analizar(guardar(d / "corrida.tif", tira(600, corrida_mm={5: 4.0}), 600))
        assert paradas(informe) == 11 and any(abs(x - 4.0) <= 0.3 for x in desplazamientos(informe)), texto(informe)

    def test_cada_linea_se_empareja_con_su_mancha_y_no_por_orden(self, d):
        """Sin la mancha de la primera parada, emparejar por orden corre todas una parada (desplazamientos de 10 mm); con la mancha más cercana, no."""
        informe = analizar(guardar(d / "sin_primera.tif", tira(600, faltan=(0,)), 600))
        assert max(desplazamientos(informe)) < 0.8 and paradas(informe) == 10, texto(informe)

    def test_con_dos_manchas_en_la_ventana_gana_la_mas_cercana(self):
        x = np.arange(300, dtype=float)
        perfil = 50 * np.exp(-0.5 * ((x - 85) / 8) ** 2) + 50 * np.exp(-0.5 * ((x - 130) / 8) ** 2)
        _, manchas, dif = rc.analizar_circulos_perfil(perfil, np.array([100]), np.array([98.0]), np.array([102.0]), 40.0, rel=7, dist=10, ventana=50)
        assert list(manchas) == [85, 130] and dif == [15]

    def test_la_ventana_de_la_mancha_es_medio_paso(self):
        perfil = np.zeros(1000)
        _, _, dif = rc.analizar_circulos_perfil(perfil, np.array([100, 500]), np.array([95, 495]), np.array([105, 505]), 0.0, ventana=50)
        assert dif == [None, None]


# ================================================================================================================ la capa verde

class TestLaCapaVerde:
    def test_se_mide_la_verde_y_no_el_gris(self, d):
        """Una tira cuya señal está solo en la azul: el gris la ve (control) y la verde no."""
        ruta = guardar(d / "solo_azul.tif", tira(600, senal="B"), 600)
        assert paradas(analizar(ruta, filtro="clahe")) == 11, "el control: el gris mezcla la azul"
        assert not distancias(analizar(ruta)) and not desplazamientos(analizar(ruta))
        midio_bien(analizar(guardar(d / "solo_verde.tif", tira(600, senal="G"), 600)), 11)

    def test_el_informe_y_la_figura_dicen_la_capa_que_se_midio(self, d):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        lienzo = FigureCanvasAgg(Figure())
        informe = analizar(guardar(d / "figura.tif", tira(600), 600), canvas=lienzo)
        assert "<b>Capa medida:</b> capa verde con CLAHE" in informe
        titulos = [ax.get_title() for ax in lienzo.figure.axes]
        assert "Perfil de intensidad invertido (capa verde con CLAHE)" in titulos and not any("rojo" in t for t in titulos), titulos

    def test_la_pagina_pide_la_capa_verde_en_sus_dos_llamadas(self):
        arbol = ast.parse((RAIZ / "ui/paginasControles/PruebasDiarias/braquiterapia.py").read_text(encoding="utf-8"))
        filtros = [k.value.value for n in ast.walk(arbol) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "analizar_lineas"
                   for k in n.keywords if k.arg == "filtro"]
        assert filtros == ["verde", "verde"], filtros

    def test_la_verde_es_el_filtro_por_omision_y_cada_filtro_nombra_su_capa(self):
        import inspect
        assert inspect.signature(rc.analizar_lineas).parameters["filtro"].default == "verde" == inspect.signature(rc.preprocesar_imagen).parameters["filtro"].default
        assert rc.CAPA_DEL_FILTRO == {"verde": "capa verde con CLAHE", "clahe": "gris con CLAHE", "bilateral": "gris binarizado", None: "capa roja"}

    def test_el_filtro_verde_es_la_capa_verde_con_el_clahe_de_siempre(self):
        import cv2
        x, y = np.arange(256)[None, :, None], np.arange(256)[:, None, None]
        bgr = (90 + x // 8 + y // 12 + np.random.default_rng(1).integers(0, 6, (256, 256, 3))).astype(np.uint8)   # dos gradientes: el límite y los mosaicos pesan
        esperado = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(np.ascontiguousarray(bgr[:, :, 1]))
        assert np.array_equal(rc.preprocesar_imagen(bgr, "verde"), esperado)


# ================================================================================================================ el informe, la página y el tiempo

@pytest.fixture(scope="module")
def pagina():
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QLabel, QWidget
    from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq
    app = QApplication.instance() or QApplication([])
    obj = PruebaDiariaBraq.__new__(PruebaDiariaBraq)
    QWidget.__init__(obj)
    obj._widgets_lazy = {}
    obj.resultado_label = QLabel()
    obj.resultado_label.setTextFormat(Qt.RichText)
    yield obj, app
    from PyQt5.QtCore import QCoreApplication, QEvent
    for w in (obj.resultado_label, obj):
        w.hide()
        w.close()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def raspar(pagina, informe):
    obj, _ = pagina
    obj.resultado_label.setText(informe)
    return obj.guardar_datos()


class TestLaPaginaGuardaLosMismosSeisNumeros:
    def test_con_lo_no_medible_la_pagina_raspa_los_mismos_numeros_del_informe(self, d, pagina):
        informe = analizar(guardar(d / "raspar.tif", tira(200, tenue=(4,)), 200))
        g = raspar(pagina, informe)
        assert g[0] == str(distancias(informe)) and g[3] == str(desplazamientos(informe))
        assert g[1] == pytest.approx(round(float(np.mean(distancias(informe))), 2)) and g[4] == pytest.approx(round(float(np.mean(desplazamientos(informe))), 2))

    @pytest.mark.parametrize("nombre, dpi, tira_kw", [("dos_paradas_a_20_mm", 600, dict(n=2, paso_mm=20.0)),
                                                       ("tres_lineas_la_del_medio_sin_mancha", 600, dict(n=3, faltan=(1,))),
                                                       ("una_sola_mancha_en_once_lineas", 200, dict(n=11, faltan=tuple(i for i in range(11) if i != 5))),
                                                       ("tres_paradas_a_20_mm", 600, dict(n=3, paso_mm=20.0))])
    def test_sin_distancias_medibles_la_pagina_no_guarda_los_desplazamientos_como_distancias(self, d, pagina, nombre, dpi, tira_kw):
        """La página lee los dos pares «Promedio»/«Desviación estándar» por orden: sin una distancia entre paradas seguidas, el par de los desplazamientos se leería como el de las distancias
        y quedaría un número falso en el registro. Las cuatro columnas de promedio y desviación quedan vacías y la lista de desplazamientos se guarda como está."""
        informe = analizar(guardar(d / f"{nombre}.tif", tira(dpi, **tira_kw), dpi))
        assert distancias(informe) == [] and desplazamientos(informe), texto(informe)
        assert raspar(pagina, informe) == ("", None, None, str(desplazamientos(informe)), None, None), texto(informe)

    def test_el_informe_no_trae_el_par_de_los_desplazamientos_sin_el_de_las_distancias(self):
        """`generar_reporte`: «Promedio» y «Desviación estándar» de los desplazamientos solo van junto a los de las distancias; la lista de desplazamientos va siempre."""
        escala, picos, diferencias = 25.4 / 600 / 10, np.array([100, 340]), [3, 5]
        con = rc.generar_reporte(picos, np.array([240.0]), escala, diferencias=diferencias)
        sin = rc.generar_reporte(picos, np.array([]), escala, diferencias=diferencias)
        assert texto(con).count("Promedio =") == 2 and texto(con).count("Desviación estándar =") == 2, texto(con)
        assert "Promedio" not in texto(sin) and "Desviaci" not in texto(sin) and desplazamientos(sin) == [0.13, 0.21], texto(sin)

    def test_sin_resolucion_confirmada_guarda_null_en_los_seis_y_no_dibuja(self, d, pagina):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        lienzo = FigureCanvasAgg(Figure())
        analizar(guardar(d / "previa.tif", tira(600), 600), canvas=lienzo)
        informe = analizar(guardar(d / "siete_pagina.png", tira(600, paso_mm=7.0), 200, "PNG"), canvas=lienzo)
        assert raspar(pagina, informe) == NADA_GUARDADO and lienzo.figure.axes == []


class TestElTiempo:
    def test_una_tira_tipica_de_600_ppp_con_su_figura_tarda_menos_de_1_s(self, d):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        ruta = guardar(d / "tiempo.tif", tira(600, n=11), 600)
        lienzo = FigureCanvasAgg(Figure())
        analizar(ruta, canvas=lienzo)
        tiempos = []
        for _ in range(3):
            t0 = time.perf_counter()
            analizar(ruta, canvas=lienzo)
            tiempos.append(time.perf_counter() - t0)
        assert min(tiempos) < 1.0, f"{tiempos} [s], carga {os.getloadavg()}"
