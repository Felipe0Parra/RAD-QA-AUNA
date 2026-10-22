"""OD.1c (PLAN_ANALISIS_PELICULAS_08-10.md, revision adicional de OD.1 del 22-10-2026): EL ENDURECIMIENTO DE OD.1.

CAUSA (logs/OD1/revision_adicional_22-10/produccion.md y pruebas.md, cada cifra vuelta a medir el 22-10 sobre el motor comiteado d5a9a51):
  OD1b-PROD-01  la regla del recorte de la netOD cuenta como «recortadas» las muestras de TINTA: una raya negra de 1 mm que cruce la banda central deja el verde, el azul y el gris «no medibles:
                la meseta esta recortada por el escaner» y en valor de pixel la misma pelicula se mide. Contar solo lo que no es tinta NO basta (la regla de la tinta es absoluta, 25 niveles bajo la mediana,
                y la meseta del mensual es oscura: la mediana minima de la zona central en las 8 peliculas del oraculo es verde 26.06, azul 32.28 y gris 18.59 contra 0.50 a 1.00 del rojo).
  OD1b-PROD-02  el umbral es absoluto, 1.5 niveles: una meseta clavada en 2 se mide y se guarda (un escaner con el negro en 2).
  OD1b-PROD-03  `leer_referencia_virgen` promete «NUNCA otra excepcion por el contenido» y un archivo anidado lanza `RecursionError`; mas ancho de lo informado: una referencia con la procedencia anidada
                600 niveles pasa `json.load` y revienta en `referencia_virgen_desde_dict`, y con la tabla de uniformidad de cualquier forma (`{}`) se acepta como valida.
  OD1b-PRU-01   ninguna prueba pulsa «Guardar» de la ventana con la base de fabrica (las 353 de E.1 corren con la base de pixel).
  OD1b-PRU-02..07  M1, M3, M5, M7 sobreviven, M2 cae solo en una prueba de A.3 que dice «mediana»; el `monkeypatch` de A.3 fija el valor que ya tiene la constante.

DECISIONES (vetables por el fisico; la primera es DE DISENO DE OPUS, tomada en la planificacion del 22-10 y aplicada tal cual):
  OD1c-D1   la regla del recorte solo se aplica a una meseta cuya MEDIANA esta cerca del negro del escaner: `NIVEL_DE_RECORTE + MARGEN_DEL_RECORTE` = 1.5 + 10.0 = 11.5 niveles o menos, y mas del 1 % de la
            zona central usable a 1.5 niveles o menos. El escaner solo puede recortar una meseta que esta a pocos ruidos de su negro (2.6 niveles de ruido como maximo): una muestra de 1.5 o menos dentro de una
            meseta de 18 niveles o mas es tinta, polvo o un rayon. Se veta quitando esa condicion (una linea) o cambiando `MARGEN_DEL_RECORTE`.
  OD1c-D2   el umbral absoluto se DOCUMENTA como limite conocido, con su prueba (cambiarlo exige el negro del escaner, una calibracion del fisico).
  OD1c-D3   el contrato de la referencia virgen se cierra donde se escribe (`pelicula.py`): `RecursionError` en `json.load`, un tope de profundidad para lo libre de la referencia (la region, la procedencia y
            los parametros: R1-PROD-01, ronda 1 de la revision) y la forma de la tabla de uniformidad.
  OD1c-D4   la prueba de A.3 cuyo nombre mentia se renombra (el `monkeypatch` se conserva: fija la premisa).

LO QUE SE GARANTIZA (cada cosa contra una verdad que NO sale del codigo bajo prueba: las rayas se dibujan en la pelicula real, el 1-D es una formula cerrada, los niveles de las regiones se ponen a mano):
  TestLaTintaNoEsRecorte             una raya de tinta no vuelve «no medible» al verde, al azul ni al gris (EPSON008.TIF y ML0, rayas de 1 y 5 mm en el crossplane y de 1 mm en el inplane).
  TestElRecorteSigueSiendoRecorte    una meseta cerca del negro con una parte recortada sigue siendo «no medible», con la frontera en la MEDIANA a 11.5 niveles.
  TestElUnoPorCientoExacto           el 1 % exacto se mide y una muestra mas no (PRU-02).
  TestElLimiteConocidoDelNegroDelEscaner  una meseta clavada en 2 niveles se mide y se puede guardar (PROD-02, limite escrito).
  TestLaReferenciaVirgenDanadaDaValueError  un archivo o una referencia danados dan `ValueError` con su motivo, y la ventana se abre diciendolo (PROD-03); la tabla de uniformidad con un NaN, un infinito o un
                                       booleano donde va un numero tambien se rechaza (R1-PRU-01).
  TestLoLibreDeLaReferenciaTieneTopeDeProfundidad  la region, la procedencia y los parametros anidan a lo sumo `PROFUNDIDAD_MAXIMA_DE_LO_LIBRE` niveles y lo que se acepta se copia y se serializa en cualquier
                                       punto de la pila (R1-PROD-01).
  TestGuardarDesdeLaVentanaEnLaBaseDeFabrica  «Guardar» de la ventana, con la base de fabrica y una pelicula real, guarda la base netOD y los numeros que la ventana muestra (PRU-01).
  TestArribaYAbajoDeLaTablaDeUniformidad / TestLasMotasNoRechazanLaVirgen / TestLaMediaDeLaVirgenApartaTambienLoClaro / TestLaComparacionConLasEsquinasUsaLaMedia  (PRU-03, PRU-04, PRU-05, PRU-07).

Rojo contra d5a9a51: caen las de la tinta (en peliculas reales y en 1-D), la frontera de 11.6 niveles, las del contrato de la referencia (menos su control) y, por API, la de las tres constantes; pasan, como
controles, las del recorte cerca del negro, 11.4 y 11.5, el limite de 2 niveles, el 1 % exacto y TODAS las de PRU-01 a PRU-07, cuyo rojo son sus mutaciones (od1_mutaciones.py, seccion OD.1c).
Esta prueba NO pide la fixture `con_la_base_de_pixel`: corre con la base de fabrica, que es justo lo que PRU-01 protege. Importa de `test_od1_densidad_optica` solo funciones y constantes (nunca una clase de
prueba) y la produccion POR PRUEBA, asi que cada una cae con su error y no con un error de coleccion que las tapa a todas. Trampa 2 (todo cuadro se parcha: la fixture `dialogos`), Trampa 9 (las ventanas las crea
y cierra `fabrica`), Trampa 10 (ningun cache de modulo; lo caro es fixture de modulo con `yield` y `gc.collect()`; un solo salto, el de la carpeta de peliculas ausente, de toda la prueba y no de un parametro).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import dataclasses
import gc
import io
import json
import math
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from matplotlib.figure import Figure
from PIL import Image

import _corpus
import _placa_mensual_sintetica as gen
from _e1_ayudas import CAPAS, USUARIO, _cursor_limpio, analizada, app, dialogos, elegir_capa, escaneo_virgen, fabrica, por_gid, texto_de_la_tabla  # noqa: F401
from test_d1_guardado_placa_mensual import _consulta, bd, clics, placa, plantilla  # noqa: F401  (las fixtures de D.1: la BD temporal y la sintetica)
from test_od1_densidad_optica import (BASE_OD, BASE_VP, CLICS, PISO_FIJADO, TAM, TODAS, _P, _dib, _pel, _pm, _referencia_con_el_piso_fijado, _svc, medir,  # noqa: F401
                                      perfil_de_dosis)

EJES = ("crossplane", "inplane")
PX_POR_MM = 600.0 / 25.4
ARCHIVO_DE_LA_REFERENCIA = "piso_pelicula_virgen.json"      # escrito AQUI a proposito: la prueba fija el nombre del archivo, no lo importa
FECHA_FIJA = "2026-03-15"                                    # la fecha con que se miden las virgenes de esta prueba: ninguna lee el reloj (DP-94, DP-155)


# ===================================================================================================== ayudas

def _ruta_de_la_pelicula(clave):
    """La ruta de una pelicula real DECLARADA en `tests/_corpus.py`. Salta la prueba entera (HI-0) si la carpeta de peliculas no la tiene; la regla de PR.0 FALLA si la carpeta existe y a la declarada le
    falta el archivo."""
    ruta = _corpus.pelicula(clave)
    if ruta is None:
        pytest.skip(f"HI-0: la pelicula {clave} no esta en {_corpus.PELICULAS_RAIZ}")
    return ruta


def _a_png(bgr):
    """Una imagen BGR como un PNG de 8 bits a 600 ppp, lo que entrega el escaner (sin perdida: la raya y la pelicula quedan exactas)."""
    b = io.BytesIO()
    Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(b, format="PNG", dpi=(600, 600))
    return b.getvalue()


def _usables_de_la_meseta(*, piso=170.0, luz_mm=99.6):
    """Los indices del perfil que `medir_perfil` cuenta como zona central USABLE (la zona central menos la marca del reticulo) con ese `luz_mm`: sobre ellos se cuenta la fraccion del recorte y se
    pone la meseta. No dependen del nivel de la meseta: salen de los bordes luminosos y del centro, que son los mismos en todos los perfiles de esta prueba."""
    limpio, centro = perfil_de_dosis(math.log10(piso / 20.0), piso=piso)
    m = medir(limpio, centro, BASE_OD, piso=piso, luz_mm=luz_mm)
    x = limpio.desde_px + np.arange(len(limpio.valores), dtype=float)
    return np.flatnonzero((x >= m.zona_px[0]) & (x <= m.zona_px[1]) & ~((x >= m.exclusion_px[0]) & (x <= m.exclusion_px[1])))


def meseta_plana(L, *, piso=170.0, nivel=None, fraccion=0.0, k=None, contigua=False, luz_mm=99.6):
    """Un perfil de dosis de 100 mm cuya zona central usable esta EXACTAMENTE en el nivel `L` (la mediana de la zona es L) y de la cual `k` muestras (o la `fraccion`) valen `nivel`: repartidas parejo por toda
    la zona o, con `contigua`, las primeras k seguidas (un pico de tinta de una sola pieza). Se mide con la netOD y el MISMO piso del perfil (con pisos distintos el FWHM sale falso).
    Devuelve (la medida, cuantas muestras usables hay, cuantas valen `nivel`, el perfil y su centro)."""
    pos = _usables_de_la_meseta(piso=piso, luz_mm=luz_mm)
    n = len(pos)
    k = int(round(fraccion * n)) if k is None else int(k)
    elegidas = np.array([], int)
    if k:
        elegidas = pos[:k] if contigua else pos[np.linspace(0, n - 1, k).round().astype(int)]
        assert len(set(elegidas.tolist())) == k

    def poner(x, v):
        v = v.copy()
        v[pos] = L
        if k:
            v[elegidas] = nivel
        return v
    perfil, centro = perfil_de_dosis(math.log10(piso / L), piso=piso, modificar=poner)
    return SimpleNamespace(medida=medir(perfil, centro, BASE_OD, piso=piso, luz_mm=luz_mm), n=n, k=k, perfil=perfil, centro=centro, posiciones=pos)


# ===================================================================================================== OD1b-PROD-01 / OD1c-D1: la tinta no es recorte

RAYAS = {"raya de 1 mm en el crossplane": (1, "crossplane"), "raya de 5 mm en el crossplane": (5, "crossplane"), "raya de 1 mm en el inplane": (1, "inplane")}


def _con_la_raya(bgr, reticulo, mm, eje):
    """La pelicula con una raya NEGRA (0 en las tres capas) de `mm` de ancho que cruza la banda central de 1 mm del perfil: en el crossplane una raya vertical a 20 mm a la derecha del reticulo, con 120 px de
    cada lado (10 mm de alto); en el inplane una horizontal a 20 mm arriba del reticulo, con 120 px de cada lado. Es el caso del hallazgo."""
    x_ret, y_ret = reticulo
    imagen = bgr.copy()
    ancho = int(round(mm * PX_POR_MM))
    if eje == "crossplane":
        x0 = int(round(x_ret + 20 * PX_POR_MM))
        imagen[y_ret - 120:y_ret + 120, x0:x0 + ancho] = 0
    else:
        y0 = int(round(y_ret - 20 * PX_POR_MM))
        imagen[y0:y0 + ancho, x_ret - 120:x_ret + 120] = 0
    return imagen


def _resumen(resultado, eje_de_la_raya):
    """Lo que esta prueba mira de un analisis, en numeros (el resultado trae la pelicula girada de 100 MB: no se retiene). `recortada_g`: la fraccion de la zona central usable del perfil del verde, en el eje de la
    raya, que vale 1.5 niveles o menos (la premisa del hallazgo, calculada aqui desde el perfil y no desde el motor)."""
    m = getattr(resultado.capas["G"], eje_de_la_raya)
    x = m.perfil.desde_px + np.arange(len(m.perfil.valores), dtype=float)
    usables = (x >= m.zona_px[0]) & (x <= m.zona_px[1]) & ~((x >= m.exclusion_px[0]) & (x <= m.exclusion_px[1]))
    valores = np.asarray(m.perfil.valores)[usables]
    svc = _svc()
    return SimpleNamespace(estado={c: resultado.capas[c].estado for c in TODAS}, fwhm={(c, e): getattr(resultado.capas[c], e).fwhm_mm for c in TODAS for e in EJES},
                           guardable={c: svc.motivo_para_no_guardar(resultado, c) is None for c in CAPAS}, recortada_g=float(np.mean(valores <= 1.5)), mediana_g=float(np.median(valores)),
                           n_usables=int(usables.sum()))


@pytest.fixture(scope="module", params=("EPSON008_TIF", "ML0"))
def pelicula_con_rayas(request):
    """Una pelicula real, limpia y con cada una de las tres rayas, cada una por el MISMO camino (cv2 -> PNG a 600 ppp -> `leer_pelicula` -> `analizar` en netOD con el piso de las esquinas): solo los numeros."""
    clave = request.param
    bgr = cv2.imread(_ruta_de_la_pelicula(clave), cv2.IMREAD_COLOR)
    clics_de_la_pelicula = CLICS[clave]
    reticulo = clics_de_la_pelicula[4]
    pel, pm = _pel(), _pm()

    def analizar(imagen, eje):
        resultado = pm.analizar(pel.leer_pelicula(_a_png(imagen)), clics_de_la_pelicula, _P(BASE_OD), modo_piso="automatico")
        resumen = _resumen(resultado, eje)
        del resultado
        gc.collect()
        return resumen

    datos = SimpleNamespace(clave=clave, limpia=analizar(bgr, "crossplane"), rayas={nombre: analizar(_con_la_raya(bgr, reticulo, mm, eje), eje) for nombre, (mm, eje) in RAYAS.items()})
    yield datos
    del bgr
    gc.collect()


class TestLaTintaNoEsRecorte:
    """OD1b-PROD-01 / OD1c-D1, sentido 1: lo que NO es recorte. Una marca de tinta, polvo o un rayon dentro de una meseta clara no la vuelve «no medible»."""

    @pytest.mark.parametrize("raya", list(RAYAS))
    def test_una_raya_negra_que_cruza_la_banda_no_vuelve_no_medible_al_verde_ni_al_azul_ni_al_gris(self, pelicula_con_rayas, raya):
        """Premisa (es el caso del hallazgo): en el perfil del verde, en el eje de la raya, MAS DEL 1 % de la zona central usable vale 1.5 niveles o menos y la mediana de esa zona esta lejos del negro. Con la
        regla de d5a9a51 eso era «recortada»; con la regla del recorte de OD1c-D1 (la mediana de la zona a 11.5 niveles o menos) es tinta. El verde y el azul quedan a 0.01 mm de la misma pelicula sin raya
        en los dos ejes; el gris, a 0.15 mm (medido 0.124 mm con la raya de 5 mm en ML0: la raya entra en su meseta, cuya mediana esta a menos de `delta_tinta` niveles de ella, como en valor de pixel);
        el rojo a 800 UM sigue «no medible» por recortado; y el verde y el azul se pueden guardar."""
        pm = _pm()
        limpia, r = pelicula_con_rayas.limpia, pelicula_con_rayas.rayas[raya]
        assert r.recortada_g > 0.01 and r.mediana_g > 20.0, (raya, r.recortada_g, r.mediana_g, "la premisa del hallazgo: la tinta pasa del 1 % de la zona y la meseta esta lejos del negro")
        for capa in ("G", "B", "gris"):
            assert r.estado[capa] == "ok", (pelicula_con_rayas.clave, raya, capa, r.estado[capa])
        for eje in EJES:
            for capa, tolerancia in (("G", 0.01), ("B", 0.01), ("gris", 0.15)):
                assert r.fwhm[(capa, eje)] == pytest.approx(limpia.fwhm[(capa, eje)], abs=tolerancia), (pelicula_con_rayas.clave, raya, capa, eje)
        assert pm.MOTIVO_MESETA_RECORTADA in r.estado["R"] and r.estado["R"].startswith("no medible"), r.estado["R"]
        assert r.guardable["G"] and r.guardable["B"], "el verde y el azul se pueden guardar con la raya"
        assert not r.guardable["R"], "el rojo a 800 UM, recortado por el escaner, no se guarda"

    def test_la_pelicula_limpia_se_mide_igual_que_siempre(self, pelicula_con_rayas):
        """El control: sin raya el verde, el azul y el gris se miden y el rojo no (nada de esto cambia con la regla nueva)."""
        r = pelicula_con_rayas.limpia
        assert [r.estado[c] for c in ("G", "B", "gris")] == ["ok", "ok", "ok"] and r.estado["R"].startswith("no medible")

    @pytest.mark.parametrize("L, nivel, fraccion, contigua, texto", [(40.0, 0.0, 0.02, True, "un pico de tinta en 0, el 2 % de una sola pieza, en una meseta de 40"),
                                                                     (33.9, 1.0, 0.02, False, "el 2 % repartido en 1.0 sobre una meseta de 33.9"),
                                                                     (33.9, 1.0, 0.30, False, "el 30 % repartido en 1.0 sobre una meseta de 33.9")], ids=["L40_pico_en_0", "L33_9_dos_por_ciento", "L33_9_treinta_por_ciento"])
    def test_un_pico_en_cero_en_medio_de_una_meseta_de_40_es_tinta_y_no_recorte(self, L, nivel, fraccion, contigua, texto):
        """El matiz del encargo, resuelto: el escaner no puede recortar una meseta de 40 niveles, asi que un 0 dentro de ella es un OBJETO (la regla de la tinta ya lo aparta de la meseta, 0 < 40 - 25) y no un
        recorte. Lo mismo con la meseta de 33.9 de siempre: aun con el 30 % de la zona a un nivel, no es el escaner. 1-D, formula cerrada: el FWHM de la dosis es 100 mm."""
        caso = meseta_plana(L, nivel=nivel, fraccion=fraccion, contigua=contigua)
        assert caso.k / caso.n > 0.01, "premisa: la tinta pasa del 1 % de la zona usable"
        assert caso.medida.ok, (texto, caso.medida.estado)
        assert caso.medida.fwhm_mm == pytest.approx(100.0, abs=0.05), texto


# ===================================================================================================== OD1b-PROD-01 / OD1c-D1: lo que SI es recorte

def _el_rojo_a_800_um():
    """El rojo de una pelicula a 800 UM: netOD de meseta 3.5 sobre un piso de 110, que la meseta caiga por debajo de 0.3 el escaner la deja en su negro."""
    perfil, centro = perfil_de_dosis(3.5, piso=110.0, modificar=lambda x, v: np.maximum(v, 0.3))
    return medir(perfil, centro, BASE_OD, piso=110.0)


class TestElRecorteSigueSiendoRecorte:
    """OD1c-D1, sentido 2: una meseta cerca del negro con una parte recortada SIGUE siendo «no medible», con el motivo de siempre."""

    @pytest.mark.parametrize("nombre", ["L 3 con el 30 % en 0.5", "L 3 con el 66 % en 0.5", "L 5 con el 2 % en 1.0", "el rojo a 800 UM (netOD 3.5, piso 110, recortado en 0.3)"],
                             ids=["L3_30", "L3_66", "L5_2", "rojo_a_800_UM"])
    def test_una_meseta_cerca_del_negro_con_una_parte_recortada_no_es_medible(self, nombre):
        casos = {"L 3 con el 30 % en 0.5": lambda: meseta_plana(3.0, nivel=0.5, fraccion=0.30).medida, "L 3 con el 66 % en 0.5": lambda: meseta_plana(3.0, nivel=0.5, fraccion=0.66).medida,
                 "L 5 con el 2 % en 1.0": lambda: meseta_plana(5.0, nivel=1.0, fraccion=0.02).medida, "el rojo a 800 UM (netOD 3.5, piso 110, recortado en 0.3)": _el_rojo_a_800_um}
        m = casos[nombre]()
        assert not m.ok and m.estado.startswith("no medible"), (nombre, m.estado)
        assert _pm().MOTIVO_MESETA_RECORTADA in m.estado and m.fwhm_mm is None, (nombre, m.estado)

    @pytest.mark.parametrize("L, se_mide", [(11.4, False), (11.5, False), (11.6, True)])
    def test_la_frontera_es_la_mediana_de_la_zona_a_once_y_medio_niveles(self, L, se_mide):
        """La regla solo mira una meseta cuya MEDIANA vale `NIVEL_DE_RECORTE + MARGEN_DEL_RECORTE` = 11.5 niveles o menos: 11.4 y 11.5 EXACTO (el `<=`) son «no medible» con el 2 % en 1.0, y 11.6 se mide.
        Premisa: la mediana de la zona es L exacto. Con 11.6 la MEDIA de la zona es 11.388 (el 2 % en 1.0 la baja): una regla que mirara la media lo daria por recortado, y esta prueba la distingue."""
        caso = meseta_plana(L, nivel=1.0, fraccion=0.02)
        valores = np.asarray(caso.perfil.valores)[caso.posiciones]
        assert float(np.median(valores)) == L and caso.k / caso.n > 0.01, "premisa: la mediana de la zona es L y la tinta pasa del 1 %"
        if se_mide:
            assert float(np.mean(valores)) < 11.5, "premisa: con la media la zona de 11.6 parece cerca del negro"
            assert caso.medida.ok, (L, caso.medida.estado)
            assert caso.medida.fwhm_mm == pytest.approx(100.0, abs=0.1)
        else:
            assert not caso.medida.ok and _pm().MOTIVO_MESETA_RECORTADA in caso.medida.estado, (L, caso.medida.estado)

    def test_la_tinta_que_es_la_mayoria_de_la_zona_tampoco_se_mide(self):
        """Si la tinta es la mayoria de la zona (el 60 % en 0.5 sobre una meseta de 20), la MEDIANA de la zona es la tinta: esta cerca del negro y la regla se aplica."""
        caso = meseta_plana(20.0, nivel=0.5, fraccion=0.60, contigua=True)
        valores = np.asarray(caso.perfil.valores)[caso.posiciones]
        assert float(np.median(valores)) == 0.5, "premisa: la mediana de la zona es la tinta"
        assert not caso.medida.ok and _pm().MOTIVO_MESETA_RECORTADA in caso.medida.estado, caso.medida.estado

    def test_las_tres_constantes_de_la_regla_son_las_de_la_decision(self):
        """Los tres numeros de la decision, escritos AQUI a proposito (la prueba fija los de la decision, no los importa): el nivel, la fraccion y el margen de la mediana."""
        pm = _pm()
        assert pm.NIVEL_DE_RECORTE == 1.5 and pm.FRACCION_DE_RECORTE_MAXIMA == 0.01 and pm.MARGEN_DEL_RECORTE == 10.0
        assert pm.NIVEL_DE_RECORTE + pm.MARGEN_DEL_RECORTE == 11.5
        assert pm.VERSION_ALGORITMO == "PM-1", "la version no sube: no hay ningun analisis netOD guardado en ninguna base (OD1c-D5)"


class TestElUnoPorCientoExacto:
    """OD1b-PRU-02: la regla es «MAS del 1 %», y el 1 % exacto se mide."""

    def test_exactamente_el_uno_por_ciento_se_mide_y_una_muestra_mas_no(self):
        """Con `luz_mm` 99.40 la zona usable tiene 1879 - 179 = 1700 muestras (premisa, contada desde `zona_px` y `exclusion_px` de la medida) y 17 / 1700 es el 1 % en float, igual al literal 0.01: 17 muestras en
        1.0 sobre una meseta de 5 es el 1 % EXACTO (no es «mas del 1 %») y se mide; 18 es mas y no. Una regla con `>=` en lugar de `>` lo desmiente."""
        uno = meseta_plana(5.0, nivel=1.0, k=17, luz_mm=99.40)
        zona, excluida = uno.medida.zona_px, uno.medida.exclusion_px
        enteros_de_la_zona = len(range(math.ceil(zona[0]), math.floor(zona[1]) + 1))
        enteros_excluidos = len(range(math.ceil(excluida[0]), math.floor(excluida[1]) + 1))
        assert enteros_de_la_zona == 1879 and enteros_excluidos == 179 and uno.n == 1700 == enteros_de_la_zona - enteros_excluidos
        assert 17 / 1700 == 0.01 == _pm().FRACCION_DE_RECORTE_MAXIMA, "premisa: 17 de 1700 es exactamente el limite, en float"
        assert uno.medida.ok, f"el 1 % exacto no es «mas del 1 %»: {uno.medida.estado}"
        mas = meseta_plana(5.0, nivel=1.0, k=18, luz_mm=99.40)
        assert not mas.medida.ok and _pm().MOTIVO_MESETA_RECORTADA in mas.medida.estado, mas.medida.estado


# ===================================================================================================== OD1b-PROD-02 / OD1c-D2: el limite conocido

def _ml0_con_el_rojo_en_2():
    """ML0 real con el rojo puesto en 2 dentro del cuadrilatero de las cuatro esquinas de `CLICS["ML0"]` encogido 4 mm hacia el cruce (la reproduccion del revisor): un escaner cuyo negro estuviera en 2."""
    bgr = cv2.imread(_ruta_de_la_pelicula("ML0"), cv2.IMREAD_COLOR)
    esquinas = np.array(CLICS["ML0"][:4], dtype=np.float64)
    cruce = np.array(CLICS["ML0"][4], dtype=np.float64)
    hacia_el_cruce = (cruce - esquinas) / np.linalg.norm(cruce - esquinas, axis=1, keepdims=True)
    encogido = esquinas + hacia_el_cruce * 4.0 * PX_POR_MM
    mascara = np.zeros(bgr.shape[:2], np.uint8)
    cv2.fillPoly(mascara, [np.rint(encogido).astype(np.int32)], 1)
    bgr[:, :, 2][mascara.astype(bool)] = 2                # el canal rojo de BGR
    return bgr


class TestElLimiteConocidoDelNegroDelEscaner:
    """OD1b-PROD-02 / OD1c-D2: el umbral de 1.5 niveles es ABSOLUTO. Con el WF-6590 de hoy el rojo recortado lee 0 o 1 (la mediana de su meseta, de 0.50 a 1.00 en las 8 peliculas) y no pasa; con un escaner
    cuyo negro estuviera en 2 o mas, una meseta recortada NO se reconoceria y daria un ancho creible. Se DOCUMENTA y se prueba (no se cambia: cambiarlo exige el negro del escaner, una calibracion del fisico).
    CONDICION DE REAPERTURA, escrita en el comentario de `NIVEL_DE_RECORTE`: si cambia el escaner o sus ajustes, medir la mediana del rojo de una pelicula a 800 UM en la zona central; si pasa de 1.5, subir
    `NIVEL_DE_RECORTE` (una linea) y esta prueba. Si alguien lo arregla, esta prueba cae y se actualiza con su motivo."""

    def test_una_meseta_clavada_en_dos_niveles_se_mide_y_se_puede_guardar_limite_conocido(self):
        pm, svc = _pm(), _svc()
        resultado = pm.analizar(_pel().leer_pelicula(_a_png(_ml0_con_el_rojo_en_2())), CLICS["ML0"], _P(BASE_OD), modo_piso="automatico")
        rojo = resultado.capas["R"]
        assert rojo.estado == "ok", rojo.estado
        assert all(math.isfinite(getattr(rojo, eje).fwhm_mm) for eje in EJES), "el rojo clavado en 2 se mide con un ancho finito (el limite conocido)"
        assert svc.motivo_para_no_guardar(resultado, "R") is None
        del resultado
        gc.collect()

    def test_una_meseta_clavada_en_dos_niveles_exactos_se_mide_en_1d_limite_conocido(self):
        """El mismo limite en 1-D, con el nivel EXACTO (la pelicula real pasa por la interpolacion del giro): una meseta de netOD 1.93 sobre piso 170 recortada en 2.0 exacto no cuenta como recortada."""
        perfil, centro = perfil_de_dosis(1.93, piso=170.0, modificar=lambda x, v: np.maximum(v, 2.0))
        m = medir(perfil, centro, BASE_OD)
        assert m.ok and _pm().MOTIVO_MESETA_RECORTADA not in m.estado, m.estado
        assert m.fwhm_mm == pytest.approx(100.0, abs=0.05)


# ===================================================================================================== OD1b-PROD-03 / OD1c-D3: la referencia virgen danada

def _anidado(niveles):
    valor = {}
    for _ in range(niveles):
        valor = {"a": valor}
    return valor


def _referencia_con_su_json(d, nota_a_mano=None):
    """El texto del archivo `piso_pelicula_virgen.json` con la referencia `d`; con `nota_a_mano`, la procedencia lleva ESE texto (JSON) en el campo `nota`, escrito a mano y no con `json.dumps`."""
    d = json.loads(json.dumps(d))
    if nota_a_mano is not None:
        d["procedencia"]["nota"] = "@@NOTA@@"
    texto = json.dumps({"version": "PV-2", "referencia": d}, ensure_ascii=False)
    return texto if nota_a_mano is None else texto.replace('"@@NOTA@@"', nota_a_mano)


class TestLaReferenciaVirgenDanadaDaValueError:
    """OD1b-PROD-03 / OD1c-D3: `leer_referencia_virgen` y `referencia_virgen_desde_dict` nunca lanzan otra cosa que `ValueError` por el contenido, y una tabla de uniformidad que no es la que escribe
    `uniformidad_y_ruido` se rechaza con su motivo."""

    @pytest.mark.parametrize("niveles", [2000, 100000])
    def test_un_json_anidado_cien_mil_niveles_es_un_archivo_danado(self, tmp_path, niveles):
        (tmp_path / ARCHIVO_DE_LA_REFERENCIA).write_text("[" * niveles + "]" * niveles, encoding="utf-8")
        with pytest.raises(ValueError) as error:
            _pel().leer_referencia_virgen(str(tmp_path))
        assert type(error.value) is ValueError, "ValueError y no una subclase ni RecursionError: la ventana solo atrapa ValueError y OSError"
        texto = str(error.value)
        assert "dañado" in texto and "anida demasiados niveles" in texto and ARCHIVO_DE_LA_REFERENCIA in texto, texto

    def test_una_procedencia_anidada_seiscientos_niveles_es_una_referencia_danada(self, escaneo_virgen, tmp_path):
        """Una referencia por lo demas valida cuya procedencia anida 600 niveles pasa `json.load` (y, sin el tope de profundidad de lo libre, reventaba en `_json_normal`, recursivo, con dos marcos por nivel).
        `referencia_virgen_desde_dict` es lo que tambien llama `svc.recalcular` con la copia guardada, asi que el contrato se cierra AHI. Y el mismo contenido escrito A MANO en el archivo."""
        pel = _pel()
        d = escaneo_virgen.referencia.como_dict()
        d["procedencia"]["nota"] = _anidado(600)
        with pytest.raises(ValueError) as error:
            pel.referencia_virgen_desde_dict(d)
        assert type(error.value) is ValueError and "anida demasiados niveles" in str(error.value), str(error.value)
        (tmp_path / ARCHIVO_DE_LA_REFERENCIA).write_text(_referencia_con_su_json(escaneo_virgen.referencia.como_dict(), '{"a": ' * 600 + "{}" + "}" * 600), encoding="utf-8")
        with pytest.raises(ValueError) as error_del_archivo:
            pel.leer_referencia_virgen(str(tmp_path))
        assert type(error_del_archivo.value) is ValueError and "anida demasiados niveles" in str(error_del_archivo.value), str(error_del_archivo.value)

    # nombre -> como se rompe la tabla de la referencia (cada caso rompe UNA cosa de la forma de `uniformidad_y_ruido`; la tabla entera y la forma derivada del productor, no una lista escrita a mano)
    TABLAS_ROTAS = {
        "un diccionario vacio": lambda d, t: d.update(uniformidad={}),
        "una clave que no es de la tabla": lambda d, t: d.update(uniformidad={"a": {}}),
        "sin las capas": lambda d, t: t.pop("capas"),
        "una clave de mas en la tabla": lambda d, t: t.update(otra=1),
        "cabe que no es booleano": lambda d, t: t.update(cabe="si"),
        "el lado de las regiones es texto": lambda d, t: t.update(lado_mm="diez"),
        "una region de mas": lambda d, t: t["regiones"].update(diagonal={"caja": None}),
        "sin la region izquierda": lambda d, t: t["regiones"].pop("izquierda"),
        "una region con una clave de mas": lambda d, t: t["regiones"]["centro"].update(otra=1),
        "una caja de 3 numeros": lambda d, t: t["regiones"]["centro"].update(caja=t["regiones"]["centro"]["caja"][:3]),
        "una caja con un texto": lambda d, t: t["regiones"]["centro"].update(caja=["a", 1, 2, 3]),
        "sin la capa azul": lambda d, t: t["capas"].pop("B"),
        "una clave de mas en una capa": lambda d, t: t["capas"]["G"].update(otra=1.0),
        "una capa sin su ruido": lambda d, t: t["capas"]["G"].pop("ruido"),
        "las regiones de una capa sin la derecha": lambda d, t: t["capas"]["R"]["regiones"].pop("derecha"),
        "la media de una region de texto": lambda d, t: t["capas"]["B"]["regiones"].update(arriba="alta"),
        "el ruido de una capa de texto": lambda d, t: t["capas"]["gris"].update(ruido="alto"),
        # R1-PRU-01 (ronda 1 de la revision): «numero» es real y FINITO y no es un booleano. Los casos de arriba usan solo texto: aflojar el validador a `isinstance(x, (int, float))` (que deja pasar NaN, infinito
        # y `true`, que JSON si lee) sobrevivia a los 22 casos. Cada sitio donde el validador exige un numero (el lado, la caja, la media de una region, las medidas de una capa) tiene su NaN o infinito y su booleano.
        "el ruido de una capa es NaN": lambda d, t: t["capas"]["G"].update(ruido=float("nan")),
        "la uniformidad de una capa es infinita": lambda d, t: t["capas"]["R"].update(uniformidad_pct=float("inf")),
        "la media de una region es infinita": lambda d, t: t["capas"]["B"]["regiones"].update(arriba=float("-inf")),
        "la media de una region es un booleano": lambda d, t: t["capas"]["B"]["regiones"].update(arriba=True),
        "una caja con un booleano": lambda d, t: t["regiones"]["centro"].update(caja=[True, 1, 2, 3]),
        "una caja con NaN": lambda d, t: t["regiones"]["centro"].update(caja=[1.0, float("nan"), 2.0, 3.0]),
        "el lado de las regiones es un booleano": lambda d, t: t.update(lado_mm=True),
        "el lado de las regiones es infinito": lambda d, t: t.update(lado_mm=float("inf")),
    }

    def test_el_servicio_dice_que_la_copia_guardada_esta_danada_y_no_lanza_recursion(self, escaneo_virgen):
        """`svc.recalcular` vuelve a leer la COPIA de la referencia virgen que viaja dentro de cada analisis guardado (DA-81) con la misma `referencia_virgen_desde_dict`: por eso el contrato se cierra ahi y no en la
        ventana. Una copia cuya procedencia anida 600 niveles da `PlacaMensualError` (un `ValueError`, el que la ventana ya atrapa al abrir un registro) y no `RecursionError`."""
        svc = _svc()
        d = escaneo_virgen.referencia.como_dict()
        d["procedencia"]["nota"] = _anidado(600)
        registro = {"piso": {"modo": "virgen", "referencia_virgen": d}, "imagen": b"", "puntos": [], "parametros": {}}
        with pytest.raises(svc.PlacaMensualError) as error:
            svc.recalcular(registro)
        assert type(error.value) is svc.PlacaMensualError and "anida demasiados niveles" in str(error.value), str(error.value)

    @pytest.mark.parametrize("nombre", list(TABLAS_ROTAS), ids=["vacia", "clave_ajena", "sin_capas", "clave_de_mas_en_la_tabla", "cabe_no_booleano", "lado_de_texto", "region_de_mas", "sin_region_izquierda",
                                                                 "region_con_clave_de_mas", "caja_de_3", "caja_con_texto", "sin_azul", "clave_de_mas_en_una_capa", "capa_sin_ruido", "capa_sin_derecha",
                                                                 "media_de_texto", "ruido_de_texto", "ruido_nan", "uniformidad_infinita", "media_infinita", "media_booleana", "caja_con_booleano",
                                                                 "caja_con_nan", "lado_booleano", "lado_infinito"])
    def test_una_tabla_de_uniformidad_que_no_es_la_de_uniformidad_y_ruido_se_rechaza(self, escaneo_virgen, nombre):
        """La referencia de `escaneo_virgen` con su tabla reemplazada por una de OTRA forma: `ValueError` cuyo texto nombra la tabla de uniformidad y ruido (antes se aceptaba y su copia viajaba en cada analisis)."""
        d = json.loads(json.dumps(escaneo_virgen.referencia.como_dict()))
        self.TABLAS_ROTAS[nombre](d, d["uniformidad"])
        with pytest.raises(ValueError) as error:
            _pel().referencia_virgen_desde_dict(d)
        assert "tabla de uniformidad y ruido" in str(error.value), (nombre, str(error.value))

    def test_la_tabla_real_y_la_de_una_zona_que_no_cabe_se_leen_igual(self, escaneo_virgen, tmp_path):
        """El control: la referencia real ida y vuelta por `guardar_referencia_virgen` / `leer_referencia_virgen` queda igual (`como_dict` igual), y la tabla que `uniformidad_y_ruido` da sobre una zona chica
        (`cabe` falso, cajas y valores en None) tambien se acepta: la validacion es la FORMA de la tabla, no que este llena."""
        pel = _pel()
        referencia = escaneo_virgen.referencia
        pel.guardar_referencia_virgen(referencia, str(tmp_path), escaneo_virgen.datos, USUARIO)
        leida = pel.leer_referencia_virgen(str(tmp_path))
        assert leida.como_dict() == referencia.como_dict() and leida.uniformidad["cabe"] is True
        planos = {c: np.zeros((1500, 1700), np.float32) for c in pel.CAPAS_DEL_PISO}
        zona = np.zeros((1500, 1700), bool)
        zona[600:900, 600:1100] = True
        chica = json.loads(json.dumps(pel.uniformidad_y_ruido(planos, zona, TAM)))
        assert chica["cabe"] is False and any(r["caja"] is None for r in chica["regiones"].values()), "premisa: una tabla de una zona que no cabe"
        d = json.loads(json.dumps(referencia.como_dict()))
        d["uniformidad"] = chica
        assert pel.referencia_virgen_desde_dict(d).uniformidad == chica

    def test_la_ventana_se_abre_con_un_archivo_anidado_y_dice_que_esta_danado(self, fabrica, dialogos, bd):
        """El archivo de 100000 niveles junto a la base ANTES de abrir la ventana: la ventana se construye (antes lanzaba `RecursionError` desde `__init__`), el menu «Piso» queda en las esquinas y la linea del
        piso lo dice. Ningun cuadro de error."""
        with open(os.path.join(os.path.dirname(bd), ARCHIVO_DE_LA_REFERENCIA), "w", encoding="utf-8") as archivo:
            archivo.write("[" * 100000 + "]" * 100000)
        v = fabrica()
        assert v.modo_del_piso == "automatico"
        assert "dañado" in v.etiqueta_piso.text() and "anida demasiados niveles" in v.etiqueta_piso.text(), v.etiqueta_piso.text()
        assert not dialogos.de("critical")


# ===================================================================================================== R1-PROD-01 (ronda 1 de la revision): lo libre de la referencia tiene un tope de profundidad

CAMPOS_LIBRES = {"procedencia": "la procedencia", "parametros": "los parámetros", "region": "la región"}      # campo de la referencia -> como lo nombra el motivo


def _profundidad_de(valor):
    """Verdad INDEPENDIENTE de la produccion, para contenidos chicos: cuantos niveles de diccionarios y listas anida `valor` (un escalar, 0; un contenedor vacio, 1). Recursiva a proposito y con UN solo marco de
    pila por nivel (un generador gastaria dos): aqui solo se miden contenidos de a lo sumo unos 500 niveles."""
    if isinstance(valor, dict):
        hijos = list(valor.values())
    elif isinstance(valor, (list, tuple)):
        hijos = list(valor)
    else:
        return 0
    mas_hondo = 0
    for hijo in hijos:
        mas_hondo = max(mas_hondo, _profundidad_de(hijo))
    return 1 + mas_hondo


def _anidado_en(niveles, forma="diccionarios"):
    """Un contenido de EXACTAMENTE `niveles` niveles (el mas hondo, vacio), de diccionarios, de listas o de tuplas (no salen de JSON, pero si de un llamador: `_json_normal` las trata como listas), armado con un bucle."""
    valor = {"diccionarios": {}, "listas": [], "tuplas": ()}[forma]
    for _ in range(niveles - 1):
        valor = {"a": valor} if forma == "diccionarios" else [valor] if forma == "listas" else (valor,)
    return valor


def _con_el_campo_libre_de(d, campo, profundidad, forma="diccionarios"):
    """Una copia de `d` cuyo `campo` (procedencia, parametros o region) conserva todo lo suyo y trae ademas una clave `libre` que lo deja con EXACTAMENTE `profundidad` niveles en total (como minimo 4: el campo
    real mas hondo, los parametros, mide 3). La profundidad se comprueba con el oraculo de arriba, no con la produccion."""
    d = json.loads(json.dumps(d))
    d[campo]["libre"] = _anidado_en(profundidad - 1, forma)
    assert _profundidad_de(d[campo]) == profundidad, "premisa de la prueba: el campo mide la profundidad pedida"
    return d


def _en_la_pila(marcos, f):
    """Llama a `f()` con `marcos` marcos de pila de mas encima: lo que se acepta tiene que seguir funcionando en cualquier punto de la pila de quien lo usa (la ventana, el servicio, otra prueba)."""
    return f() if marcos == 0 else _en_la_pila(marcos - 1, f)


def _lo_que_sigue(referencia, carpeta):
    """Lo que se hace DESPUES de leer una referencia: copiarla (`como_dict`), serializarla estricta como lo hace el servicio al guardar el analisis, y guardarla junto a la base como lo hace la ventana.
    «sigue_ok», o «RecursionError» si la pila se agota (el defecto)."""
    try:
        json.dumps(referencia.como_dict(), allow_nan=False)
        _pel().guardar_referencia_virgen(referencia, str(carpeta), None, USUARIO)
        return "sigue_ok"
    except RecursionError:
        return "RecursionError"


class TestLoLibreDeLaReferenciaTieneTopeDeProfundidad:
    """R1-PROD-01 (revision de la ronda 1 de OD.1c). La region, la procedencia y los parametros de una referencia no tienen forma fija (de ellos solo se exige que sean un diccionario) y
    `referencia_virgen_desde_dict` los copia con `_json_normal` (recursivo, dos marcos de pila por nivel). Sin un tope de profundidad, de 13 a unos 470 niveles se ACEPTABAN como validos (su copia viajaba en cada
    analisis guardado: la CAUSA 3 del plan) y, segun la pila de quien guardaba despues, `como_dict()` o `json.dumps` lanzaban `RecursionError` y no `ValueError` (medido: 440 niveles aceptados leyendo con la
    pila baja y rotos al guardar con 60 marcos mas). Ahora lo libre anida a lo sumo `PROFUNDIDAD_MAXIMA_DE_LO_LIBRE` niveles, medido sin recursion: lo que la aplicacion escribe llega a 3, y lo que se acepta
    se copia y se serializa en cualquier punto de la pila."""

    def test_lo_que_la_aplicacion_escribe_cabe_con_holgura(self, escaneo_virgen):
        """La premisa del tope, medida en la referencia real de la aplicacion: la procedencia y la region anidan 2 niveles y los parametros 3. El tope deja al menos el triple; si la aplicacion pasara a escribir mas
        hondo, esta prueba lo dice antes de que `referencia_virgen_desde_dict` rechace una referencia propia."""
        pel = _pel()
        d = json.loads(json.dumps(escaneo_virgen.referencia.como_dict()))
        reales = {campo: _profundidad_de(d[campo]) for campo in CAMPOS_LIBRES}
        assert reales == {"procedencia": 2, "parametros": 3, "region": 2}, reales
        assert 3 * max(reales.values()) <= pel.PROFUNDIDAD_MAXIMA_DE_LO_LIBRE
        assert pel.referencia_virgen_desde_dict(d).como_dict() == escaneo_virgen.referencia.como_dict()

    @pytest.mark.parametrize("forma", ["diccionarios", "listas", "tuplas"])
    @pytest.mark.parametrize("campo", list(CAMPOS_LIBRES))
    def test_el_tope_exacto_se_acepta_y_un_nivel_mas_no(self, escaneo_virgen, campo, forma):
        """En cada campo libre y en las tres formas de anidar (diccionarios, listas y tuplas): el tope exacto se lee y se serializa; un nivel mas es `ValueError` (solo `ValueError`) que nombra el campo y el tope."""
        pel = _pel()
        tope = pel.PROFUNDIDAD_MAXIMA_DE_LO_LIBRE
        base = escaneo_virgen.referencia.como_dict()
        aceptada = pel.referencia_virgen_desde_dict(_con_el_campo_libre_de(base, campo, tope, forma))
        assert _profundidad_de(getattr(aceptada, campo)) == tope
        json.dumps(aceptada.como_dict(), allow_nan=False)
        with pytest.raises(ValueError) as error:
            pel.referencia_virgen_desde_dict(_con_el_campo_libre_de(base, campo, tope + 1, forma))
        texto = str(error.value)
        assert type(error.value) is ValueError and "dañada" in texto and CAMPOS_LIBRES[campo] in texto and "anida demasiados niveles" in texto and str(tope) in texto, texto

    @pytest.mark.parametrize("niveles", [50, 100, 300, 450])
    @pytest.mark.parametrize("campo", list(CAMPOS_LIBRES))
    def test_un_anidamiento_de_cientos_de_niveles_es_una_referencia_danada_y_no_se_acepta_como_valida(self, escaneo_virgen, campo, niveles):
        """La CAUSA 3 del plan: «anidada 100 a 450 niveles ... se acepta como valida y su copia viajaria en cada analisis guardado». Sin el tope se aceptaban en la procedencia, los parametros y la region."""
        d = _con_el_campo_libre_de(escaneo_virgen.referencia.como_dict(), campo, niveles)
        with pytest.raises(ValueError) as error:
            _pel().referencia_virgen_desde_dict(d)
        assert type(error.value) is ValueError and "anida demasiados niveles" in str(error.value) and CAMPOS_LIBRES[campo] in str(error.value), str(error.value)

    def test_lo_que_se_acepta_sigue_funcionando_en_cualquier_punto_de_la_pila(self, escaneo_virgen, tmp_path):
        """El hueco que vio la revision, sin depender de que pila tenga la prueba: para CADA contenido que `referencia_virgen_desde_dict` acepta (leyendo con la pila baja), copiarlo, serializarlo y guardarlo
        funciona con 10, 60, 120 y 300 marcos de pila de mas. Sin el tope, los de unos 400 a 470 niveles se aceptaban y se rompian despues con la pila mas honda (`RecursionError`); se barren de 5 en 5 niveles porque
        la ventana de niveles que se acepta y se rompe mide unos 55 y su lugar depende de la pila con que corra la prueba."""
        pel = _pel()
        base = escaneo_virgen.referencia.como_dict()
        aceptados, rotos = [], []
        for niveles in list(range(4, 13)) + list(range(300, 500, 5)):
            d = _con_el_campo_libre_de(base, "procedencia", niveles)
            try:
                referencia = _en_la_pila(10, lambda: pel.referencia_virgen_desde_dict(d))
            except ValueError:
                continue
            aceptados.append(niveles)
            for marcos in (10, 60, 120, 300):
                destino = tmp_path / f"{niveles}_{marcos}"
                if _en_la_pila(marcos, lambda: _lo_que_sigue(referencia, destino)) != "sigue_ok":
                    rotos.append((niveles, marcos))
        assert not rotos, f"se aceptaron y se rompieron despues (niveles, marcos de pila de mas): {rotos[:6]}"
        assert aceptados and min(aceptados) == 4, "premisa: lo chico se acepta"

    def test_un_contenido_que_se_contiene_a_si_mismo_es_una_referencia_danada(self, escaneo_virgen):
        """Control: un diccionario que se contiene a si mismo (no sale de JSON, pero sale de un llamador) no cuelga ni lanza `RecursionError`: `ValueError` con su motivo."""
        d = json.loads(json.dumps(escaneo_virgen.referencia.como_dict()))
        d["parametros"]["otra_vez"] = d["parametros"]
        with pytest.raises(ValueError) as error:
            _pel().referencia_virgen_desde_dict(d)
        assert type(error.value) is ValueError and "anida demasiados niveles" in str(error.value), str(error.value)

    def test_un_archivo_con_lo_libre_anidado_a_mano_dice_que_esta_danado(self, escaneo_virgen, tmp_path):
        """El mismo contenido, escrito en el archivo junto a la base (50 niveles en los parametros: pasa `json.load` y antes se aceptaba): `leer_referencia_virgen` da `ValueError` con la ruta del archivo."""
        d = json.loads(json.dumps(escaneo_virgen.referencia.como_dict()))
        d["parametros"]["libre"] = _anidado(50)
        (tmp_path / ARCHIVO_DE_LA_REFERENCIA).write_text(json.dumps({"version": "PV-2", "referencia": d}, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ValueError) as error:
            _pel().leer_referencia_virgen(str(tmp_path))
        texto = str(error.value)
        assert type(error.value) is ValueError and ARCHIVO_DE_LA_REFERENCIA in texto and "no se puede usar" in texto and "los parámetros anida demasiados niveles" in texto, texto


# ===================================================================================================== OD1b-PRU-01: «Guardar» con la base de fabrica

def _ejes_de_los_perfiles(v):
    ejes = list(v._fig_perfiles.axes)
    assert len(ejes) == 8
    return ejes


class TestGuardarDesdeLaVentanaEnLaBaseDeFabrica:
    """OD1b-PRU-01: las 353 pruebas de E.1 corren con la base de pixel y comparan contra ese mismo diccionario; en `TestLaVentana` de OD.1 el unico `svc.guardar` es directo. Aqui la ventana, con la base de
    FABRICA y una pelicula real, pulsa «Guardar», y lo guardado es lo que la pantalla mostro, en la base con que la pantalla midio."""

    @pytest.fixture(autouse=True)
    def _la_base_de_fabrica_es_la_netod(self):
        """La premisa de toda la clase, escrita AQUI: si una fixture de modulo de otro archivo dejara la base de pixel puesta (E.1 las usa), esto cae y lo dice."""
        pm = _pm()
        assert pm.VALORES_DE_LA_GEOMETRIA["base_de_la_medida"] == pm.BASE_POR_OMISION == BASE_OD == "densidad óptica neta"

    def test_guardar_con_la_capa_verde_guarda_la_base_netod_y_los_numeros_que_se_ven(self, fabrica, dialogos, bd):
        pm, dib, svc = _pm(), _dib(), _svc()
        v = fabrica()
        analizada(v, dialogos, _ruta_de_la_pelicula("EPSON008_TIF"), CLICS["EPSON008_TIF"])
        assert v._resultado.base == BASE_OD and v.capa_reportada == "G" and svc.motivo_para_no_guardar(v._resultado, "G") is None
        mostrado = pm.valores_medidos(v._resultado, "G")
        columna = dib.COLUMNAS_DE_LOS_PERFILES.index("FWHM [mm]")
        verde = dib.nombre_de_la_capa("G")
        textos = [fila[columna] for fila in texto_de_la_tabla(v.tabla_perfiles) if fila[0] == verde]          # el FWHM del verde: [crossplane, inplane]
        assert len(textos) == 2 and textos == [dib.numero(mostrado["fwhm_crossplane_mm"], 3), dib.numero(mostrado["fwhm_inplane_mm"], 3)]
        v.boton_guardar.click()
        registro = svc.leer(v.ref_de_prueba)
        assert registro["parametros"]["base_de_la_medida"] == BASE_OD, "«Guardar» guarda la base con que la pantalla midio"
        assert registro["parametros"] == pm.VALORES_DE_LA_GEOMETRIA and len(registro["parametros"]) == 41
        assert {k: registro[k] for k in mostrado} == mostrado, "los siete datos finales guardados son EXACTAMENTE los que la ventana mostro"
        assert textos == [dib.numero(registro["fwhm_crossplane_mm"], 3), dib.numero(registro["fwhm_inplane_mm"], 3)]
        for eje, indice in (("crossplane", 0), ("inplane", 1)):
            luz = v._resultado.bordes_luz_px[eje]
            ancho_de_la_luz = (luz[1] - luz[0]) * v._resultado.tam_mm
            assert abs(registro[f"fwhm_{eje}_mm"] - ancho_de_la_luz) < 1.0, (eje, registro[f"fwhm_{eje}_mm"], ancho_de_la_luz, "en netOD el verde queda a menos de 1 mm del campo luminoso; en valor de pixel saldria de +0.9 a +2.6")

    def test_reabrir_lo_guardado_mide_en_netod_sin_diferencias_ni_avisos(self, fabrica, dialogos, bd):
        svc = _svc()
        v = fabrica()
        analizada(v, dialogos, _ruta_de_la_pelicula("EPSON008_TIF"), CLICS["EPSON008_TIF"])
        v.boton_guardar.click()
        dialogos.llamadas.clear()
        w = fabrica(ref=v.ref_de_prueba)
        assert w.estado == "registro" and w._resultado.base == BASE_OD
        assert svc.diferencias(svc.leer(v.ref_de_prueba), w._resultado) == []
        assert not dialogos.de("warning") and not dialogos.de("critical")
        assert [ax.get_ylabel() for ax in _ejes_de_los_perfiles(w)] == ["densidad óptica neta [1]"] * 8
        assert w.etiqueta_piso.text().startswith("Base de la medida: densidad óptica neta"), w.etiqueta_piso.text()

    def test_reabrir_con_la_constante_cambiada_a_pixel_sigue_midiendo_con_la_base_guardada(self, fabrica, dialogos, bd, monkeypatch):
        """DA-81 por la ventana: la copia guardada manda. Con la constante de fabrica cambiada a valor de pixel DESPUES de guardar, el registro se reabre en netOD, sin diferencias ni avisos."""
        pm, svc = _pm(), _svc()
        v = fabrica()
        analizada(v, dialogos, _ruta_de_la_pelicula("EPSON008_TIF"), CLICS["EPSON008_TIF"])
        v.boton_guardar.click()
        dialogos.llamadas.clear()
        monkeypatch.setitem(pm.VALORES_DE_LA_GEOMETRIA, "base_de_la_medida", BASE_VP)
        w = fabrica(ref=v.ref_de_prueba)
        assert w.estado == "registro" and w._resultado.base == BASE_OD, "la base del registro, no la de hoy"
        assert svc.diferencias(svc.leer(v.ref_de_prueba), w._resultado) == []
        assert not dialogos.de("warning") and not dialogos.de("critical")

    def test_con_la_pelicula_virgen_vigente_se_guarda_su_copia_y_la_base_netod(self, fabrica, dialogos, bd, escaneo_virgen):
        """Una referencia «ok» armada como la del piso fijado de OD.1 (los valores de `PISO_FIJADO`) pero con la tabla de uniformidad de una virgen real y el margen con que se midio, para que pase por
        `referencia_virgen_desde_dict` como una guardada de verdad, escrita junto a la base ANTES de abrir la ventana: el modo es «virgen», lo guardado lleva la COPIA de la referencia y la base netOD."""
        pel, pm, dib, svc = _pel(), _pm(), _dib(), _svc()
        referencia = dataclasses.replace(_referencia_con_el_piso_fijado(), uniformidad=escaneo_virgen.referencia.uniformidad, parametros={"margen_borde_virgen_mm": 2.0})
        pel.guardar_referencia_virgen(referencia, os.path.dirname(bd), None, USUARIO)
        v = fabrica()
        assert v.modo_del_piso == "virgen", "premisa: con una referencia vigente el menu arranca en la virgen"
        analizada(v, dialogos, _ruta_de_la_pelicula("EPSON008_TIF"), CLICS["EPSON008_TIF"])
        assert v._resultado.piso.modo == "virgen" and svc.motivo_para_no_guardar(v._resultado, "G") is None
        mostrado = pm.valores_medidos(v._resultado, "G")
        v.boton_guardar.click()
        registro = svc.leer(v.ref_de_prueba)
        assert registro["piso"]["modo"] == "virgen" and registro["parametros"]["base_de_la_medida"] == BASE_OD
        assert registro["piso"]["referencia_virgen"]["capas"]["G"]["media"] == PISO_FIJADO["G"] == 194.05, "la copia de la referencia viaja con el analisis"
        assert {k: registro[k] for k in mostrado} == mostrado
        verde = dib.nombre_de_la_capa("G")
        assert [fila[dib.COLUMNAS_DE_LOS_PERFILES.index("FWHM [mm]")] for fila in texto_de_la_tabla(v.tabla_perfiles) if fila[0] == verde] == \
            [dib.numero(registro["fwhm_crossplane_mm"], 3), dib.numero(registro["fwhm_inplane_mm"], 3)]

    def test_la_capa_roja_a_800_um_no_se_puede_guardar_y_la_ventana_dice_el_motivo(self, fabrica, dialogos, bd, monkeypatch):
        """El caso real a 800 UM, que ninguna prueba ejercia por la ventana: con la capa roja elegida «Guardar» queda apagado, la linea de la regla dice el motivo de la meseta recortada y nombra el verde y el
        azul como las que si se pueden guardar; llamar `_al_guardar` por codigo no llama al servicio ni deja fila; y elegir de nuevo el verde lo habilita SIN recalcular."""
        svc = _svc()
        v = fabrica()
        analizada(v, dialogos, _ruta_de_la_pelicula("EPSON008_TIF"), CLICS["EPSON008_TIF"])
        resultado = v._resultado
        llamadas = []
        original = svc.guardar
        monkeypatch.setattr(svc, "guardar", lambda *a, **k: llamadas.append(a) or original(*a, **k))
        elegir_capa(v, "R")
        assert not v.boton_guardar.isEnabled()
        texto = v.linea_regla.text()
        assert _pm().MOTIVO_MESETA_RECORTADA in texto and "verde" in texto and "azul" in texto, texto
        v._al_guardar()
        assert llamadas == [] and _consulta(bd, "SELECT COUNT(*) FROM analisis_placa_mensual WHERE ref = ?", (v.ref_de_prueba,)) == [(0,)]
        elegir_capa(v, "G")
        assert v.boton_guardar.isEnabled() and v._resultado is resultado, "elegir la capa no recalcula"


# ===================================================================================================== OD1b-PRU-03: arriba y abajo de la tabla de uniformidad

def _planos_con_las_regiones():
    """Planos de 1500 x 1700 constantes por capa, con +2 alrededor del centro de «arriba» (cy - my, con la geometria del docstring de `uniformidad_y_ruido`), -2 en «abajo», +4 en «izquierda» y -4 en
    «derecha»: cuadrados de 300 px (la caja de una region mide 236) que no se tocan entre si. Devuelve (planos, zona, niveles de base, centros esperados)."""
    alto, ancho = 1500, 1700
    base = {"R": 100.0, "G": 150.0, "B": 80.0, "gris": 120.0}
    planos = {c: np.full((alto, ancho), base[c], np.float32) for c in base}
    cy, cx = (alto - 1) / 2, (ancho - 1) / 2
    my, mx = (alto - 1) / 4, (ancho - 1) / 4
    centros = {"centro": (cy, cx), "arriba": (cy - my, cx), "abajo": (cy + my, cx), "izquierda": (cy, cx - mx), "derecha": (cy, cx + mx)}
    cambios = {"arriba": 2.0, "abajo": -2.0, "izquierda": 4.0, "derecha": -4.0}
    for nombre, delta in cambios.items():
        yc, xc = centros[nombre]
        y0, x0 = int(round(yc - 150)), int(round(xc - 150))
        for c in planos:
            planos[c][y0:y0 + 300, x0:x0 + 300] += delta
    return planos, np.ones((alto, ancho), bool), base, cambios


class TestArribaYAbajoDeLaTablaDeUniformidad:
    """OD1b-PRU-03: ninguna prueba fijaba DONDE quedan «arriba» y «abajo» (el eje y de la imagen apunta hacia abajo): intercambiarlas cruzaba las columnas del cuadro de la virgen, las cajas dibujadas y la copia
    JSON que viaja con cada analisis."""

    def test_arriba_es_la_region_de_menor_y_y_abajo_la_de_mayor_y(self):
        planos, zona, base, cambios = _planos_con_las_regiones()
        u = _pel().uniformidad_y_ruido(planos, zona, TAM)
        assert u["cabe"] is True
        for capa, nivel in base.items():
            fila = u["capas"][capa]
            assert fila["centro"] == nivel
            for nombre, delta in cambios.items():
                assert fila["regiones"][nombre] == nivel + delta, (capa, nombre, "cada region da el nivel que se puso en SU lugar")
        cajas = {nombre: r["caja"] for nombre, r in u["regiones"].items()}
        assert cajas["arriba"][1] < cajas["centro"][1] < cajas["abajo"][1], "arriba tiene la y menor y abajo la mayor"
        assert cajas["izquierda"][0] < cajas["centro"][0] < cajas["derecha"][0], "izquierda tiene la x menor y derecha la mayor"

    def test_la_tabla_y_el_dibujo_ponen_cada_region_en_su_columna_y_en_su_lugar(self):
        dib = _dib()
        planos, zona, base, cambios = _planos_con_las_regiones()
        tabla = _pel().uniformidad_y_ruido(planos, zona, TAM)
        referencia = SimpleNamespace(uniformidad=json.loads(json.dumps(tabla)))
        filas = dib.filas_de_la_uniformidad(referencia)
        columnas = dib.COLUMNAS_DE_LA_UNIFORMIDAD
        for fila, (capa, nivel) in zip(filas, base.items()):
            for rotulo, nombre in (("Arriba [nivel]", "arriba"), ("Abajo [nivel]", "abajo"), ("Izquierda [nivel]", "izquierda"), ("Derecha [nivel]", "derecha")):
                assert fila[columnas.index(rotulo)] == dib.numero(nivel + cambios[nombre], 2), (capa, rotulo)
        ax = Figure().add_subplot()
        dib.dibujar_regiones_de_la_virgen(ax, referencia)
        y = {nombre: float(np.mean(por_gid(ax, f"virgen:region:{nombre}")[0].get_ydata())) for nombre in ("arriba", "centro", "abajo")}
        assert y["arriba"] < y["centro"] < y["abajo"], "en el dibujo, arriba queda por encima (y menor) del centro y abajo por debajo"


# ===================================================================================================== OD1b-PRU-04, 05 y 07: la pelicula virgen

def _arreglo_de_la_virgen(semilla=1):
    """El arreglo (uint8) de una pelicula VIRGEN sintetica (la del generador con la meseta = virgen, sin dosis ni tinta, el fondo del escaner puro): la de E.1, sin codificar para poder tocarla."""
    calibracion = dict(gen.CALIB, meseta_bgr=gen.CALIB["virgen_bgr"], fondo_escaner=255.0)
    arreglo, _ = gen.generar_arreglo(variante="A", theta_deg=0.0, bits=8, dpi=600, tinta=False, calib=calibracion, seed=semilla)
    arreglo = np.array(arreglo)
    arreglo[arreglo.min(axis=2) >= 235] = 255
    return arreglo


def _medir_la_virgen(arreglo):
    datos = gen.codificar(np.clip(arreglo, 0, 255).astype(np.uint8), "tiff", 600)
    return _pel().piso_de_pelicula_virgen(datos, _P(), "virgen_lote.tif", fecha_calculo=FECHA_FIJA)


@pytest.fixture(scope="module")
def virgen_limpia():
    """La virgen sintetica sin tocar y su referencia, una vez por modulo."""
    arreglo = _arreglo_de_la_virgen()
    yield SimpleNamespace(arreglo=arreglo, referencia=_medir_la_virgen(arreglo))
    gc.collect()


class TestLasMotasNoRechazanLaVirgen:
    """OD1b-PRU-04 / OD1-D14: que C6 «nunca rechaza» solo se probaba hasta el 4.6 % de motas; un rechazo reintroducido por encima del 5 % no lo veia nadie."""

    def test_una_virgen_con_casi_un_veinte_por_ciento_de_motas_es_valida_con_su_aviso(self, virgen_limpia):
        """1800 motas de 7 x 7 px, +60 niveles (0.3 mm, claras), en posiciones al azar con semilla fija: con su halo cubren casi el 19 % de la zona medida (medido 18.898 %). La referencia es valida, C6 AVISA con
        esa fraccion, ninguna comprobacion rechaza, y el valor del verde esta a 0.15 niveles del de la virgen limpia (medido 0.0002: las motas se apartan)."""
        img = virgen_limpia.arreglo.astype(np.int16)
        alto, ancho = img.shape[:2]
        rng = np.random.default_rng(5)
        for y, x in zip(rng.integers(100, alto - 100, 1800), rng.integers(100, ancho - 100, 1800)):
            img[y:y + 7, x:x + 7, :] += 60
        ref = _medir_la_virgen(img)
        resultados = {p.nombre: p for p in ref.pruebas}
        assert ref.estado == "ok", ref.estado
        assert resultados["C6 motas"].resultado == "aviso" and not [p for p in ref.pruebas if p.resultado == "rechazo"], [(p.nombre, p.resultado) for p in ref.pruebas]
        fraccion = float(resultados["C6 motas"].texto.split("motas en el ")[1].split(" %")[0])
        assert fraccion >= 15.0, resultados["C6 motas"].texto
        assert abs(ref.valor("G") - virgen_limpia.referencia.valor("G")) <= 0.15


class TestLaMediaDeLaVirgenApartaTambienLoClaro:
    """OD1b-PRU-05: el corte de la media de la virgen (lo que se aparta mas de `delta_tinta` niveles de la mediana) es por los DOS lados; solo una prueba de A.3 cuyo nombre decia «mediana» lo vigilaba."""

    def test_los_pixeles_claros_aislados_no_suben_el_valor_de_la_virgen(self, virgen_limpia):
        """Un pixel claro (+60 niveles) de cada 16, aislados: la media de la zona medida subiria 3.75 niveles (premisa, calculada en la zona medida del verde) y el valor de la virgen (la media SIN lo que se
        aparta mas de `delta_tinta` de la mediana, por arriba y por abajo) queda a 0.15 niveles del de la limpia en R, G, B y gris (medido 0.000; con el corte solo por abajo, +3.750)."""
        img = virgen_limpia.arreglo.astype(np.int16)
        img[::4, ::4, :] += 60
        ref = _medir_la_virgen(img)
        assert ref.estado == "ok", ref.estado
        x0, y0, x1, y1 = ref.region["caja"]
        zona = np.array(np.clip(img, 0, 255)[y0:y1, x0:x1, 1], np.float64)
        assert zona.mean() - np.median(zona) > 3.0, "premisa: la media de la zona del verde pasa de la mediana en mas de 3 niveles"
        for capa in TODAS:
            assert abs(ref.valor(capa) - virgen_limpia.referencia.valor(capa)) <= 0.15, capa


@pytest.fixture(scope="module")
def pelicula_con_su_campo():
    """La sintetica de PF.0 en TIFF de 8 bits (theta 0.4, semilla 1) con las cuatro esquinas de su campo luminoso, y su piso automatico (el de las esquinas) en niveles."""
    s = gen.generar("tiff", variante="A", theta_deg=0.4, seed=1)
    pelicula = _pel().leer_pelicula(s.datos)
    m = s.verdad.marcas_px
    campo = [m["UL"], m["UR"], m["DR"], m["DL"]]
    automatico = _pel().piso_de_pelicula(pelicula, campo, _P(), modo="automatico")
    assert automatico.estado == "ok", automatico.estado
    yield SimpleNamespace(pelicula=pelicula, campo=campo, automatico={c: automatico.capas[c].mediana for c in TODAS})
    gc.collect()


def _referencia_de_la_virgen(valores_automaticos, medias, medianas):
    """Una `ReferenciaVirgen` valida armada en Python (8 bits, TIFF, 600 ppp que coincide): cada capa con su MEDIA y su MEDIANA a la distancia dada del piso automatico de la pelicula."""
    pel = _pel()
    capas = {c: pel.CapaDelPiso(c, "ok", valores_automaticos[c] + medianas[c], 1000, 1.0, None, None, valores_automaticos[c] + medias[c]) for c in TODAS}
    procedencia = {"archivo": "virgen_de_prueba.tif", "sha256": "ab" * 32, "bytes": 1, "formato": "TIFF", "bits": 8, "dpi_declarado": 600.0, "clase_resolucion": "coincide", "forma": [100, 100],
                   "fecha_escaneo": None, "equipo": None, "calidad_jpeg": None, "submuestreo": None, "orientacion_declarada": None, "fecha_calculo": FECHA_FIJA, "version": pel.VERSION_PISO_VIRGEN}
    return pel.ReferenciaVirgen("ok", capas, (), (), {"caja": [0, 0, 1, 1], "n": 1000, "area_mm2": 1.0}, procedencia, {})


class TestLaComparacionConLasEsquinasUsaLaMedia:
    """OD1b-PRU-07: la comparacion de la virgen con el piso automatico de la misma pelicula (la virgen mas oscura, a 3 niveles; el aviso del azul, a 5; el del verde, a 25) usa el MISMO numero que el piso, la
    MEDIA (`valor`), y no la mediana. Se arma la referencia con la media y la mediana a uno y otro lado de cada frontera."""

    # (capa, media, mediana, lo que debe pasar): las demas capas a +2 / +2
    CASOS = [("G", -3.5, +1.0, "mas oscura"), ("G", +1.0, -3.5, "ok"), ("gris", -3.5, +1.0, "mas oscura"), ("R", -3.5, +1.0, "mas oscura"), ("B", +5.5, +4.5, "aviso del azul"),
             ("B", +4.5, +5.5, "sin aviso del azul"), ("G", +26.0, +24.0, "aviso del verde"), ("G", +24.0, +26.0, "sin aviso del verde")]

    @pytest.mark.parametrize("capa, media, mediana, esperado", CASOS, ids=[f"{c[0]}_{c[1]:+g}_{c[2]:+g}" for c in CASOS])
    def test_la_comparacion_sigue_a_la_media_y_no_a_la_mediana(self, pelicula_con_su_campo, capa, media, mediana, esperado):
        s = pelicula_con_su_campo
        medias, medianas = {c: 2.0 for c in TODAS}, {c: 2.0 for c in TODAS}
        medias[capa], medianas[capa] = media, mediana
        piso = _pel().piso_de_pelicula(s.pelicula, s.campo, _P(), modo="virgen", referencia_virgen=_referencia_de_la_virgen(s.automatico, medias, medianas))
        avisos = " ".join(piso.avisos)
        if esperado == "mas oscura":
            assert piso.estado.startswith("no medible: la película virgen es más oscura que la película de fuera del campo"), piso.estado
            return
        assert piso.estado == "ok", piso.estado
        assert ("El azul de la película virgen difiere" in avisos) == (esperado == "aviso del azul"), (esperado, avisos)
        assert ("El verde de la película virgen está" in avisos) == (esperado == "aviso del verde"), (esperado, avisos)
