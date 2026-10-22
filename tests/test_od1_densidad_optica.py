"""OD.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-87): LA DENSIDAD OPTICA NETA REEMPLAZA AL VALOR DE PIXEL COMO BASE DEL ANALISIS MENSUAL, con el piso de la pelicula virgen.

CAUSA (medida el 21-10 sobre el motor comiteado, logs/OD/): en valor de pixel normalizado el verde sale mas ancho que el campo luminoso (de +1.0 a +2.4 mm en siete peliculas) y en netOD = log10(I0 / v)
queda a +-1 mm; el rojo a 800 UM esta recortado por el escaner (66 a 99.6 % de su meseta en <= 1.5 niveles) y no tiene netOD. DECISIONES DEL FISICO (no volver a preguntar): la netOD REEMPLAZA a la base
con la MISMA zona, meseta, tinta, contraste, bordes, barrido y lo MISMO guardado; se cambia en UNA constante y cada analisis guarda la que uso; la pelicula virgen se escanea APARTE y UNA vez, se ve su
uniformidad y su ruido como el Catphan y su MEDIA por capa es el piso; todo escaneo es TIFF a 600 ppp.

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale del codigo bajo prueba (formulas cerradas, el generador independiente de PF.0 y los numeros del pre-vuelo de Opus en logs/OD/):
  (a) LA FORMULA Y SU MONOTONIA: n = log10(piso / max(v, 0.5)) / log10(piso / max(meseta, 0.5)); 0 en el piso, 1 en la meseta, 0.5 en la media geometrica; con la base de pixel nada cambia (bit a bit).
  (b) VERDAD CONOCIDA 1-D: un borde de dosis erf de penumbra conocida con PV = I0 * 10^(-ODm * D): la netOD da el FWHM de la DOSIS a 0.05 mm o menos con netOD de meseta 0.2, 0.7 y 1.2 y el valor
      de pixel lo agranda justo lo que predice d* = (log10 2 - log10(1 + 10^(-ODm))) / ODm.
  (c) LA IMAGEN CONVERTIDA PIXEL A PIXEL (la «imagen con la densidad optica aplicada» del fisico) da los mismos bordes que la base netOD a 0.02 mm o menos: en la sintetica de PF.0 y en las peliculas reales
      EPSON008.TIF, EPSON001.TIF y EPSON007, SIN EXCEPCION. La banda de 1 mm se promedia como esa imagen convertida (la media de log10 por pixel, `perfil_central(..., base=)`), asi que una mota brillante
      dentro de la banda ya no acorta el azul (EPSON007 y EPSON008.TIF inplane: 95.85 y 96.04 mm con el promedio lineal, 98.78 y 99.03 con el de los logaritmos). Decision OD1-REV-D1 (opcion B, de Opus,
      vetable por el fisico): `TestLaImagenConvertidaEnPeliculasReales`, `TestElPromedioDeLaBandaEsElDeLaImagenConvertida` (la banda de una `CapaGirada` disenada) y el AST de `perfil_central`.
  (d) EL RECORTE: mas del 1 % de la zona central en 1.5 niveles o menos es «no medible» con su motivo, solo en netOD.
  (e) PELICULAS REALES (TIFF primero): con el piso de las esquinas y con el piso fijado en los valores del pre-vuelo los FWHM del verde, el azul y el gris, a 0.011 mm; el rojo, «no medible». Los cuatro
      del azul inplane de EPSON007 y EPSON008.TIF (y el gris crossplane de EPSON029 con las esquinas, que con B queda 1.5e-5 fuera) toman el valor de la imagen convertida pixel a pixel, medido por una ruta
      independiente (decision OD1-REV-D1); la tolerancia no cambia.
  (f) LA PELICULA VIRGEN REAL: EPSON179 aceptada con su MEDIA por capa y su tabla de uniformidad y ruido; EPSON178 rechazada solo por el rango; (f-bis) las piezas de 10 x 10 cm y la hoja sin fondo.
  (g) `modo_efectivo`: la UNICA regla del modo (la virgen si hay referencia y las esquinas si no; un modo pedido se respeta).
  (h) LA BASE DE IDA Y VUELTA POR D.1: un registro netOD se recalcula en netOD aunque cambie la constante; uno sin el parametro, en valor de pixel; ninguna columna nueva.
  (i) LA VENTANA: el menu «Piso» arranca en el modo efectivo, la referencia vigente se usa sola, el cuadro de la virgen muestra su uniformidad y su ruido sin simbolos, los perfiles se dibujan en la base.
  (j) UNA CONSTANTE POR DECISION: cambiar `BASE_POR_OMISION` o `MODO_DEL_PISO_POR_OMISION` en una linea cambia el defecto.

Rojo contra HEAD (6c26026): HEAD no tiene la base netOD, `modo_efectivo`, la media de la virgen ni su uniformidad; las pruebas que usan nombres nuevos caen con su error y las que miden (las peliculas
reales, el verde en netOD) caen por su asercion. Las pruebas de este archivo importan la produccion POR PRUEBA, asi que cada una cae con su error y no como un error de coleccion que las tapa a todas.
Trampa 2 (todo `QMessageBox` y cuadro se parcha: la fixture `dialogos`), Trampa 9 (ventanas cerradas con la receta completa), Trampa 10 (ningun `lru_cache` ni cache de modulo: lo caro es fixture de modulo).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import copy
import dataclasses
import gc
import importlib
import io
import json
import math
import re
import sys
import types
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image
from matplotlib.figure import Figure
from scipy.special import erf, erfinv

import _corpus
import _placa_mensual_sintetica as gen
from _e1_ayudas import (CAPAS, USUARIO, _cursor_limpio, analizada, app, archivo_placa, cargar, clic, dialogos, escaneo_virgen, fabrica, marcar, por_gid, sin_simbolos,  # noqa: F401
                        todos_los_textos)
from test_d1_guardado_placa_mensual import bd, clics, placa, plantilla  # noqa: F401  (fixtures de D.1: la BD temporal, la sintetica y sus clics)

RAIZ = Path(__file__).resolve().parent.parent
TAM = 25.4 / 600.0
BASE_OD = "densidad óptica neta"                 # escritas AQUI a proposito: la prueba fija los textos, no los importa
BASE_VP = "valor de píxel normalizado"
VP_MINIMO = 0.5
EJES = ("crossplane", "inplane")
TODAS = ("R", "G", "B", "gris")
SIMBOLOS = "✓✗✔✘⚠❌✅❎☑☒"


def _pm():
    return importlib.import_module("analisisImagenes.placa_mensual")


def _pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _dib():
    return importlib.import_module("analisisImagenes.dibujo_placa_mensual")


def _svc():
    return importlib.import_module("services.placa_mensual")


def _P(base=BASE_OD, **cambios):
    """Los parametros de fabrica con la base pedida (escrita a mano: en HEAD el parametro no existe y el motor lo ignora)."""
    return {**_pm().VALORES_DE_LA_GEOMETRIA, "base_de_la_medida": base, **cambios}


def od(piso, v):
    """La densidad optica neta de un nivel: log10(I0 / v), con el piso de VP_MINIMO (el ORACULO: formula cerrada)."""
    return math.log10(piso / max(v, VP_MINIMO))


# ===================================================================================================== (a) la formula y su monotonia

class TestLaFormulaYSuMonotonia:
    PISO, MESETA = 170.0, 33.0

    def test_la_base_se_llama_densidad_optica_neta_y_es_la_de_omision(self):
        pm = _pm()
        assert pm.BASE_DENSIDAD_OPTICA == BASE_OD and pm.BASE_VALOR_DE_PIXEL == BASE_VP
        assert set(pm.BASES) == {BASE_OD, BASE_VP} and len(pm.BASES) == 2
        assert pm.BASE_POR_OMISION == pm.BASE_DENSIDAD_OPTICA == BASE_OD, "la netOD es la base por omision (decision del fisico del 21-10)"
        assert pm.VP_MINIMO == VP_MINIMO

    def test_cero_en_el_piso_uno_en_la_meseta_y_medio_en_la_media_geometrica(self):
        pm = _pm()
        piso, meseta = self.PISO, self.MESETA
        n = pm.normalizar(BASE_OD, [piso, meseta, math.sqrt(piso * meseta)], piso, meseta)
        assert n == pytest.approx([0.0, 1.0, 0.5], abs=1e-12)
        assert pm.nivel_de_la_base(BASE_OD, 0.5, piso, meseta) == pytest.approx(math.sqrt(piso * meseta), abs=1e-9), "la altura media en niveles es la media GEOMETRICA, no la aritmetica"
        assert pm.nivel_de_la_base(BASE_OD, 0.5, piso, meseta) < (piso + meseta) / 2.0 - 10, "la media geometrica queda muy por debajo de la aritmetica"

    @pytest.mark.parametrize("v", [0.1, 0.4, 0.5, 1.0, 7.3, 33.0, 80.0, 170.0, 200.0])
    def test_coincide_con_la_formula_cerrada_incluido_el_piso_del_logaritmo(self, v):
        pm = _pm()
        esperado = od(self.PISO, v) / od(self.PISO, self.MESETA)
        assert float(pm.normalizar(BASE_OD, [v], self.PISO, self.MESETA)[0]) == pytest.approx(esperado, rel=1e-12, abs=1e-12)

    def test_por_debajo_de_medio_nivel_el_logaritmo_se_detiene(self):
        """Un nivel de 0 (el escaner recorto) no tiene logaritmo: se toma medio nivel, nunca infinito ni NaN."""
        pm = _pm()
        n = pm.normalizar(BASE_OD, [0.0, 0.2, 0.5], self.PISO, self.MESETA)
        assert np.isfinite(n).all() and n[0] == n[1] == n[2]

    def test_es_monotona_decreciente_en_el_valor_de_pixel(self):
        pm = _pm()
        v = np.linspace(self.PISO, 1.0, 400)
        n = pm.normalizar(BASE_OD, v, self.PISO, self.MESETA)
        assert np.all(np.diff(n) > 0), "a menor valor de pixel (mas oscuro), mayor netOD"

    def test_un_nan_sigue_siendo_nan(self):
        pm = _pm()
        n = pm.normalizar(BASE_OD, np.array([100.0, np.nan, 50.0]), self.PISO, self.MESETA)
        assert np.isnan(n[1]) and np.isfinite(n[[0, 2]]).all()

    def test_con_la_base_de_pixel_nada_cambia_ni_un_bit(self):
        pm = _pm()
        v = np.array([170.0, 150.5, 99.9, 33.0, 12.25])
        assert np.array_equal(pm.normalizar(BASE_VP, v, 170.0, 33.0), (170.0 - v) / (170.0 - 33.0))
        for f in (0.2, 0.5, 0.8):
            assert pm.nivel_de_la_base(BASE_VP, f, 170.0, 33.0) == 170.0 - f * (170.0 - 33.0)

    @pytest.mark.parametrize("base", [BASE_OD, BASE_VP])
    @pytest.mark.parametrize("f", [0.2, 0.5, 0.8])
    def test_el_nivel_de_una_fraccion_es_el_que_la_normalizacion_devuelve_como_esa_fraccion(self, base, f):
        pm = _pm()
        nivel = pm.nivel_de_la_base(base, f, self.PISO, self.MESETA)
        assert float(pm.normalizar(base, [nivel], self.PISO, self.MESETA)[0]) == pytest.approx(f, abs=1e-12)

    def test_valores_en_la_base_para_dibujar(self):
        pm = _pm()
        v = np.array([170.0, 85.0, 33.0, 0.0])
        assert np.array_equal(pm.valores_en_la_base(BASE_VP, v, 170.0), v), "en valor de pixel el eje es el nivel de 8 bits, sin tocarlo"
        sale = pm.valores_en_la_base(BASE_OD, v, 170.0)
        assert sale == pytest.approx([0.0, math.log10(2.0), od(170.0, 33.0), od(170.0, 0.0)], abs=1e-12) and sale[0] == 0.0
        assert float(pm.valores_en_la_base(BASE_OD, 33.0, 170.0)) == pytest.approx(od(170.0, 33.0), abs=1e-12), "tambien un escalar (el nivel de la meseta, de la altura media...)"

    def test_una_base_que_no_existe_es_value_error_y_dice_las_dos(self):
        pm = _pm()
        for funcion in (lambda b: pm.normalizar(b, [1.0], 170.0, 33.0), lambda b: pm.nivel_de_la_base(b, 0.5, 170.0, 33.0), lambda b: pm.valores_en_la_base(b, [1.0], 170.0)):
            with pytest.raises(ValueError) as e:
                funcion("dosis absoluta")
            assert BASE_OD in str(e.value) and BASE_VP in str(e.value)


# ===================================================================================================== (j) una constante por decision

def _modulo_con_la_linea_cambiada(archivo, antes, despues, nombre):
    """El modulo `archivo` ejecutado con UNA linea cambiada (en un espacio de nombres aparte: el real no se toca). La linea tiene que existir una sola vez."""
    texto = (RAIZ / archivo).read_text(encoding="utf-8")
    assert texto.count(antes) == 1, f"la linea «{antes}» tiene que existir exactamente una vez en {archivo}"
    modulo = types.ModuleType(nombre)
    modulo.__file__ = str(RAIZ / archivo)
    sys.modules[nombre] = modulo                       # los dataclasses con anotaciones de texto buscan su modulo en sys.modules mientras se definen
    try:
        exec(compile(texto.replace(antes, despues), str(RAIZ / archivo), "exec"), modulo.__dict__)
    finally:
        sys.modules.pop(nombre, None)
    return modulo


class TestUnaConstantePorDecision:
    def test_la_base_por_omision_se_cambia_en_una_linea_y_cambia_el_parametro_que_viaja(self):
        pm = _pm()
        otro = _modulo_con_la_linea_cambiada("analisisImagenes/placa_mensual.py", "BASE_POR_OMISION = BASE_DENSIDAD_OPTICA", "BASE_POR_OMISION = BASE_VALOR_DE_PIXEL", "pm_con_pixel_por_omision")
        assert otro.VALORES_DE_LA_GEOMETRIA["base_de_la_medida"] == otro.BASE_VALOR_DE_PIXEL
        assert otro.PARAMETROS["base_de_la_medida"]["valor"] == otro.BASE_VALOR_DE_PIXEL
        assert pm.VALORES_DE_LA_GEOMETRIA["base_de_la_medida"] == BASE_OD, "el modulo real no se toco"

    def test_el_parametro_base_de_la_medida_tiene_su_motivo_y_dice_las_opciones(self):
        pm = _pm()
        entrada = pm.PARAMETROS["base_de_la_medida"]
        assert entrada["valor"] == pm.BASE_POR_OMISION and entrada["unidad"] and len(entrada["motivo"]) > 80
        assert BASE_OD in entrada["motivo"] and BASE_VP in entrada["motivo"], "el motivo dice las dos opciones y donde se cambia"
        assert "BASE_POR_OMISION" in entrada["motivo"]
        assert len(pm.VALORES_DE_LA_GEOMETRIA) == 41 and pm.VALORES_DE_LA_GEOMETRIA["base_de_la_medida"] == BASE_OD, "los 40 de siempre y el de la base"
        assert pm.VERSION_ALGORITMO == "PM-1", "la version no sube: la base viaja en los parametros guardados (vetable OD1-D1)"

    def test_el_modo_del_piso_por_omision_se_cambia_en_una_linea(self):
        pel = _pel()
        assert pel.MODO_DEL_PISO_POR_OMISION == "virgen" and pel.MODOS_DEL_PISO == ("automatico", "punto_manual", "virgen") and pel.CAPA_POR_OMISION == "G"
        otro = _modulo_con_la_linea_cambiada("analisisImagenes/pelicula.py", 'MODO_DEL_PISO_POR_OMISION = "virgen"', 'MODO_DEL_PISO_POR_OMISION = "automatico"', "pel_con_automatico_por_omision")
        referencia = object()
        assert otro.modo_efectivo(None, referencia) == "automatico", "con esa linea, el defecto ya no es la virgen aunque haya referencia"
        assert pel.modo_efectivo(None, referencia) == "virgen"

    def test_con_el_punto_marcado_como_modo_por_omision_y_sin_punto_el_modo_efectivo_son_las_esquinas(self):
        otro = _modulo_con_la_linea_cambiada("analisisImagenes/pelicula.py", 'MODO_DEL_PISO_POR_OMISION = "virgen"', 'MODO_DEL_PISO_POR_OMISION = "punto_manual"', "pel_con_punto_por_omision")
        assert otro.modo_efectivo(None, object()) == "automatico", "sin un punto marcado no hay punto_manual que tomar: el piso sale de las esquinas"
        assert otro.modo_efectivo(None, None, (1.0, 2.0)) == "punto_manual"

    def test_la_constante_de_la_base_se_define_una_vez_y_el_parametro_la_usa_por_nombre(self):
        arbol = ast.parse((RAIZ / "analisisImagenes" / "placa_mensual.py").read_text(encoding="utf-8"))
        asignaciones = [n for n in arbol.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "BASE_POR_OMISION" for t in n.targets)]
        assert len(asignaciones) == 1 and isinstance(asignaciones[0].value, ast.Name) and asignaciones[0].value.id == "BASE_DENSIDAD_OPTICA"
        literales = [n.lineno for n in ast.walk(arbol) if isinstance(n, ast.Constant) and n.value == BASE_OD]
        assert len(literales) == 1, f"el texto «{BASE_OD}» se escribe una sola vez (BASE_DENSIDAD_OPTICA): {literales}"


# ===================================================================================================== (b) verdad conocida 1-D

def perfil_de_dosis(od_meseta, *, piso=170.0, ancho_mm=100.0, sigma_mm=2.3, n=3400, centro=1700.0, desde=0, eje="crossplane", capa="G", modificar=None):
    """Un perfil de pelicula con dosis relativa D (la diferencia de dos erf de ancho `ancho_mm` y penumbra `sigma_mm`; D = 0.5 EXACTAMENTE en +-ancho/2) y respuesta lineal en netOD:
    PV = piso * 10^(-od_meseta * D). El FWHM de la DOSIS es `ancho_mm`. Devuelve (PerfilCentral, centro_px)."""
    pm = _pm()
    x = desde + np.arange(n, dtype=float)
    u = (x - centro) * TAM
    D = 0.5 * (erf((u + ancho_mm / 2) / (math.sqrt(2) * sigma_mm)) - erf((u - ancho_mm / 2) / (math.sqrt(2) * sigma_mm)))
    v = piso * 10.0 ** (-od_meseta * D)
    if modificar is not None:
        v = modificar(x, v)
    perfil = pm.PerfilCentral(capa=capa, eje=eje, banda=0, valores=np.asarray(v, dtype=np.float64), desde_px=desde, filas_px=(0.0, 24.0), n_filas=24, tam_mm=TAM)
    return perfil, float(centro)


def medir(perfil, centro, base, *, piso=170.0, luz_mm=99.6, reticulo_mm=0.0, **cambios):
    pm = _pm()
    luz = (centro - luz_mm / 2 / TAM, centro + luz_mm / 2 / TAM)
    return pm.medir_perfil(perfil, centro, piso, base, _P(base, **cambios), luz, centro + reticulo_mm / TAM)


def desplazamiento_del_pixel(od_meseta, sigma_mm=2.3):
    """El oraculo de d*: cuanto MAS ANCHO sale el FWHM con la base de pixel que con la dosis (mm). El 50 % del valor de pixel normalizado cae donde la dosis vale
    d* = (log10 2 - log10(1 + 10^(-ODm))) / ODm; en el borde, D(u) = 0.5 (1 - erf((u - w/2) / (sqrt2 sigma))), asi que el borde queda en w/2 + sqrt2 sigma erfinv(1 - 2 d*) a cada lado."""
    d_estrella = (math.log10(2.0) - math.log10(1.0 + 10.0 ** (-od_meseta))) / od_meseta
    return 2.0 * math.sqrt(2.0) * sigma_mm * float(erfinv(1.0 - 2.0 * d_estrella)), d_estrella


class TestVerdadConocidaEnUnaDimension:
    @pytest.mark.parametrize("od_meseta", [0.2, 0.7, 1.2])
    def test_la_netod_da_el_ancho_de_la_dosis(self, od_meseta):
        perfil, centro = perfil_de_dosis(od_meseta)
        m = medir(perfil, centro, BASE_OD)
        assert m.ok, m.estado
        assert m.fwhm_mm == pytest.approx(100.0, abs=0.05), (od_meseta, m.fwhm_mm)
        assert m.centro_rad_px == pytest.approx(centro, abs=0.05 / TAM)

    @pytest.mark.parametrize("od_meseta", [0.2, 0.7, 1.2])
    def test_el_valor_de_pixel_lo_agranda_justo_lo_que_predice_d_estrella(self, od_meseta):
        perfil, centro = perfil_de_dosis(od_meseta)
        m = medir(perfil, centro, BASE_VP)
        extra, d_estrella = desplazamiento_del_pixel(od_meseta)
        assert m.ok and d_estrella < 0.5
        assert m.fwhm_mm == pytest.approx(100.0 + extra, abs=0.05), (od_meseta, m.fwhm_mm, 100.0 + extra)
        assert m.fwhm_mm > 100.0 + 0.5, "en valor de pixel el campo sale mas ancho que la dosis: 0.66, 2.19 y 3.41 mm con netOD de meseta 0.2, 0.7 y 1.2"

    def test_cuanto_mas_oscura_la_meseta_mas_se_agranda_el_valor_de_pixel_y_la_netod_no(self):
        anchos_vp, anchos_od = [], []
        for od_meseta in (0.2, 0.7, 1.2):
            perfil, centro = perfil_de_dosis(od_meseta)
            anchos_vp.append(medir(perfil, centro, BASE_VP).fwhm_mm)
            anchos_od.append(medir(perfil, centro, BASE_OD).fwhm_mm)
        assert anchos_vp[0] < anchos_vp[1] < anchos_vp[2]
        assert max(anchos_od) - min(anchos_od) < 0.05

    def test_la_penumbra_80_20_de_la_netod_es_la_de_la_dosis(self):
        """La penumbra 80-20 de la dosis erf es 2 * 0.8416 * sigma = 3.87 mm; la netOD la da (el valor de pixel la da distinta)."""
        perfil, centro = perfil_de_dosis(0.7)
        esperada = 2.0 * float(erfinv(0.6)) * math.sqrt(2.0) * 2.3
        m = medir(perfil, centro, BASE_OD)
        assert m.ok and all(p == pytest.approx(esperada, abs=0.06) for p in m.penumbras_mm), (m.penumbras_mm, esperada)

    def test_el_nivel_de_la_altura_media_que_dice_la_medida_es_el_de_la_base(self):
        perfil, centro = perfil_de_dosis(0.7)
        mo, mp = medir(perfil, centro, BASE_OD), medir(perfil, centro, BASE_VP)
        assert mo.altura_media == pytest.approx(math.sqrt(mo.piso * mo.meseta), abs=1e-9)
        assert mp.altura_media == pytest.approx(mp.piso - 0.5 * (mp.piso - mp.meseta), abs=1e-9)
        assert mo.altura_media < mp.altura_media - 5, "la misma meseta tiene una altura media mas baja en netOD (media geometrica)"
        assert mo.nivel_penumbra_alta == pytest.approx(mo.piso * (mo.meseta / mo.piso) ** 0.8, abs=1e-9)
        assert mo.nivel_penumbra_baja == pytest.approx(mo.piso * (mo.meseta / mo.piso) ** 0.2, abs=1e-9)

    def test_la_meseta_de_un_perfil_es_la_media_de_los_niveles_en_las_dos_bases(self):
        """La meseta que se normaliza es la media de los NIVELES de la zona, sin tinta (D.1 guarda lo mismo que antes); la netOD de la meseta se obtiene de ella. Es la misma en las dos bases."""
        perfil, centro = perfil_de_dosis(0.7, modificar=lambda x, v: v + 3.0 * np.sin(x / 7.0))
        mo, mp = medir(perfil, centro, BASE_OD), medir(perfil, centro, BASE_VP)
        x = np.arange(len(perfil.valores), dtype=float)
        zona = (x >= mo.zona_px[0]) & (x <= mo.zona_px[1]) & ~((x >= mo.exclusion_px[0]) & (x <= mo.exclusion_px[1]))
        assert mo.meseta == mp.meseta == pytest.approx(float(perfil.valores[zona].mean()), abs=1e-9)
        assert mo.muestras_meseta == mp.muestras_meseta


# ===================================================================================================== (d) el recorte

def posiciones_usables_de_la_meseta():
    """Los indices del perfil de dosis de netOD 0.7 que `medir_perfil` cuenta como zona central USABLE (la zona central menos la marca del reticulo): sobre ellos se cuenta la fraccion de la regla del recorte."""
    limpio, centro = perfil_de_dosis(0.7)
    m = medir(limpio, centro, BASE_OD)
    x = limpio.desde_px + np.arange(len(limpio.valores), dtype=float)
    usables = (x >= m.zona_px[0]) & (x <= m.zona_px[1]) & ~((x >= m.exclusion_px[0]) & (x <= m.exclusion_px[1]))
    return np.flatnonzero(usables)


def perfil_con_k_muestras_en(k, nivel, posiciones):
    """El perfil de dosis de netOD 0.7 con EXACTAMENTE `k` de las muestras usables de la meseta puestas en `nivel`, repartidas parejo por toda la zona: (perfil, centro)."""
    elegidas = posiciones[np.linspace(0, len(posiciones) - 1, k).round().astype(int)]
    assert len(set(elegidas.tolist())) == k

    def poner(x, v):
        v = v.copy()
        v[elegidas] = nivel
        return v
    return perfil_de_dosis(0.7, modificar=poner)


class TestElRecorteEsNoMedible:
    def test_una_meseta_recortada_no_tiene_netod_y_dice_por_que(self):
        pm = _pm()
        perfil, centro = perfil_de_dosis(3.5, piso=110.0, modificar=lambda x, v: np.maximum(v, 0.3))      # un rojo a 800 UM: la meseta, que cae por debajo de 0.3, el escaner la deja en su piso
        m = medir(perfil, centro, BASE_OD, piso=110.0)
        assert not m.ok and m.estado.startswith("no medible")
        assert pm.MOTIVO_MESETA_RECORTADA == "la meseta está recortada por el escáner" and pm.MOTIVO_MESETA_RECORTADA in m.estado
        assert m.fwhm_mm is None and m.bordes_rad_px == (None, None)

    def test_con_el_valor_de_pixel_la_misma_meseta_se_mide_igual_que_siempre(self):
        perfil, centro = perfil_de_dosis(3.5, piso=110.0, modificar=lambda x, v: np.maximum(v, 0.3))
        m = medir(perfil, centro, BASE_VP, piso=110.0)
        assert m.ok and m.fwhm_mm > 100.0, "el recorte es una regla de la netOD: en valor de pixel el rojo se mide (mas ancho) como en HEAD"

    @pytest.mark.parametrize("fraccion, mide", [(0.0, True), (0.004, True), (0.02, False), (0.30, False)])
    def test_la_regla_es_mas_del_uno_por_ciento_de_la_zona_en_un_nivel_y_medio_o_menos(self, fraccion, mide):
        """Las muestras recortadas se reparten por TODA la zona (cada k-esima), a niveles de 1.0 (<= 1.5)."""
        def con_recorte(x, v):
            if fraccion > 0:
                paso = max(2, int(round(1.0 / fraccion)))
                v = v.copy()
                v[(np.arange(len(v)) % paso == 0) & (np.abs(x - 1700.0) * TAM < 38.0)] = 1.0
            return v
        perfil, centro = perfil_de_dosis(0.7, modificar=con_recorte)
        m = medir(perfil, centro, BASE_OD)
        if mide:
            assert m.ok, (fraccion, m.estado)
        else:
            assert not m.ok and _pm().MOTIVO_MESETA_RECORTADA in m.estado, (fraccion, m.estado)

    def test_un_nivel_de_dos_no_esta_recortado(self):
        """El umbral es 1.5 niveles: una meseta de 2 niveles (netOD enorme pero real) se mide."""
        perfil, centro = perfil_de_dosis(1.93, piso=170.0, modificar=lambda x, v: np.maximum(v, 2.0))
        m = medir(perfil, centro, BASE_OD)
        assert "recortada" not in m.estado

    def test_el_recorte_se_cuenta_solo_en_la_zona_central_y_no_en_todo_el_perfil(self):
        """La regla es de la MESETA (la zona central, a +-40 % del ancho luminoso): un tramo del perfil casi negro FUERA de ella (una mancha de tinta entre su limite, a 39.8 mm, y el borde del campo, a 49.8)
        no es una meseta recortada. El tramo es el 7 % del perfil entero: si la regla mirara todo el perfil, lo rechazaria."""
        def tinta_afuera(x, v):
            u = np.abs(x - 1700.0) * TAM
            v = v.copy()
            v[(u > 41.0) & (u < 46.0)] = 0.3
            return v
        perfil, centro = perfil_de_dosis(0.7, modificar=tinta_afuera)
        afuera = np.asarray(perfil.valores) <= 1.5
        assert 0.05 < afuera.mean() < 0.09, "premisa: el tramo oscuro es el 7 % del perfil"
        m = medir(perfil, centro, BASE_OD)
        assert m.ok and _pm().MOTIVO_MESETA_RECORTADA not in m.estado, m.estado
        assert m.fwhm_mm == pytest.approx(100.0, abs=0.1)

    def test_las_dos_constantes_de_la_regla_son_las_del_plan(self):
        """OD1-REV-PRU-04: «mas del 1 % de la zona central en 1.5 niveles o menos». Los dos numeros estan escritos AQUI a proposito (la prueba fija los del plan, no los importa)."""
        pm = _pm()
        assert pm.FRACCION_DE_RECORTE_MAXIMA == 0.01 and pm.NIVEL_DE_RECORTE == 1.5

    def test_el_uno_por_ciento_es_la_frontera_y_se_cuenta_estrictamente_mas(self):
        """OD1-REV-PRU-04: un poco menos del 1 % de la zona usable (0.94 %) se mide y un poco mas (1.06 %) es «no medible»; los casos de arriba (0.4 % y 2 %) estaban lejos del umbral y una fraccion de 1.5 % o de
        0.5 % no los distinguia de la del plan. Las muestras recortadas se cuentan EXACTAS sobre la zona que mide `medir_perfil` (no por un paso que reparte)."""
        posiciones = posiciones_usables_de_la_meseta()
        n = len(posiciones)
        k_debajo, k_encima = int(math.floor(0.0094 * n)), int(math.ceil(0.0106 * n))
        assert k_debajo / n < 0.01 < k_encima / n and k_encima > k_debajo, (n, k_debajo, k_encima)
        perfil, centro = perfil_con_k_muestras_en(k_debajo, 1.0, posiciones)
        m = medir(perfil, centro, BASE_OD)
        assert m.ok and _pm().MOTIVO_MESETA_RECORTADA not in m.estado, (k_debajo / n, m.estado)
        perfil, centro = perfil_con_k_muestras_en(k_encima, 1.0, posiciones)
        m = medir(perfil, centro, BASE_OD)
        assert not m.ok and _pm().MOTIVO_MESETA_RECORTADA in m.estado, (k_encima / n, m.estado)

    @pytest.mark.parametrize("nivel, recortada", [(1.0, True), (1.4, True), (1.5, True), (1.6, False), (1.7, False), (1.8, False)])
    def test_un_nivel_y_medio_o_menos_es_recortado_y_apenas_encima_no(self, nivel, recortada):
        """OD1-REV-PRU-04: con el 2 % de la zona (el doble de lo que tolera la regla, para que solo el NIVEL decida) a `nivel`: 1.5 EXACTO cuenta como recortado («o menos») y 1.6 no. Los casos de arriba usaban 1.0 y 2.0,
        lejos del umbral, y un nivel de 1.9 o de 1.2 en lugar de 1.5 no se veia."""
        posiciones = posiciones_usables_de_la_meseta()
        k = int(math.ceil(0.02 * len(posiciones)))
        perfil, centro = perfil_con_k_muestras_en(k, nivel, posiciones)
        m = medir(perfil, centro, BASE_OD)
        if recortada:
            assert not m.ok and _pm().MOTIVO_MESETA_RECORTADA in m.estado, (nivel, m.estado)
        else:
            assert m.ok and _pm().MOTIVO_MESETA_RECORTADA not in m.estado, (nivel, m.estado)


# ===================================================================================================== (c) la imagen convertida pixel a pixel

@pytest.fixture(scope="module")
def sintetica():
    placa = gen.generar("tiff", variante="A", theta_deg=0.4, seed=1)
    verdad = placa.verdad
    pelicula = _pel().leer_pelicula(placa.datos)
    puntos = [verdad.marcas_px[k] for k in ("UL", "UR", "DR", "DL", "C")]
    yield types.SimpleNamespace(verdad=verdad, pelicula=pelicula, puntos=puntos, datos=placa.datos)


@pytest.fixture(scope="module")
def analisis_od(sintetica):
    """El analisis netOD de la sintetica con el piso automatico, una vez por modulo (su pelicula girada pesa unos 125 MB)."""
    yield _pm().analizar(sintetica.pelicula, sintetica.puntos, _P(BASE_OD), modo_piso="automatico")
    gc.collect()


class TestLaImagenConvertidaPixelAPixelDaLoMismo:
    """(c) en la placa SINTETICA de PF.0 (sin motas). Las peliculas reales, con la mota brillante del azul, las cubre `TestLaImagenConvertidaEnPeliculasReales` (tambien sin excepcion: decision OD1-REV-D1)."""
    PISO_C, K = 200.0, 100.0

    @pytest.mark.parametrize("capa", ["G", "B", "gris"])
    def test_los_bordes_de_la_netod_son_los_de_la_imagen_en_densidad_optica_medida_con_la_base_de_pixel_en_la_sintetica(self, analisis_od, capa):
        pm = _pm()
        r = analisis_od
        assert r.ok and r.base == BASE_OD and r.capas[capa].ok, (r.estado, r.capas[capa].estado)
        piso = r.capas[capa].piso
        original = r.girada.capa(capa)
        convertida = np.where(np.isfinite(original.datos), self.PISO_C - self.K * np.log10(piso / np.maximum(original.datos.astype(np.float64), VP_MINIMO)), np.nan)
        capa_c = dataclasses.replace(original, datos=convertida)
        for i, eje in enumerate(EJES):
            perfil = pm.perfil_central(capa_c, eje, _P(BASE_VP))
            m = pm.medir_perfil(perfil, r.girada.cruce[i], self.PISO_C, BASE_VP, _P(BASE_VP), r.bordes_luz_px[eje], r.geometria.reticulo_girado[i])
            esperado = getattr(r.capas[capa], eje)
            assert m.ok and esperado.ok, (capa, eje, m.estado, esperado.estado)
            for b_conv, b_od in zip(m.bordes_rad_px, esperado.bordes_rad_px):
                assert abs(b_conv - b_od) * TAM <= 0.02, (capa, eje, b_conv, b_od)
            assert m.fwhm_mm == pytest.approx(esperado.fwhm_mm, abs=0.02)

    def test_en_valor_de_pixel_la_misma_pelicula_da_otros_bordes_asi_que_la_comparacion_discrimina(self, sintetica):
        pm = _pm()
        vp = pm.analizar(sintetica.pelicula, sintetica.puntos, _P(BASE_VP), modo_piso="automatico")
        od_ = pm.analizar(sintetica.pelicula, sintetica.puntos, _P(BASE_OD), modo_piso="automatico")
        assert vp.base == BASE_VP and od_.base == BASE_OD
        assert vp.capas["G"].crossplane.fwhm_mm - od_.capas["G"].crossplane.fwhm_mm > 0.5, "el verde en valor de pixel sale mas ancho que en netOD"
        assert vp.capas["B"].crossplane.fwhm_mm != od_.capas["B"].crossplane.fwhm_mm


PELICULAS_DE_LA_IMAGEN_CONVERTIDA = ("EPSON008_TIF", "EPSON001_TIF", "EPSON007")        # los recortes de 2.7 mil px (rapidas); las paginas enteras no hacen falta para fijar la relacion


@pytest.fixture(scope="module")
def contra_la_imagen_convertida():
    """{(pelicula, capa, eje): (FWHM de produccion en netOD, FWHM de la imagen girada convertida PIXEL A PIXEL y medida en la base de pixel, bordes de produccion, bordes de la convertida, FWHM del ATAJO)} de las
    peliculas reales de `PELICULAS_DE_LA_IMAGEN_CONVERTIDA`, con el piso de las esquinas: el procedimiento de (c) (w = 200 - 100 log10(piso / max(v, 0.5)), `perfil_central` y `medir_perfil` en valor de pixel).
    El ATAJO es lo que hacia la netOD antes de la decision OD1-REV-D1: el PROMEDIO LINEAL de la banda (la linea de valor de pixel de `perfil_central`) y despues el logaritmo, medido con `medir_perfil` en netOD;
    sirve de control (la prueba de la mota exige que el atajo SI acortara el azul, o la prueba no discriminaria)."""
    pm = _pm()
    salida = {}
    for clave in PELICULAS_DE_LA_IMAGEN_CONVERTIDA:
        ruta = _corpus.pelicula(clave)
        if ruta is None:
            pytest.skip(f"HI-0: la pelicula real {clave} no esta")
        r = pm.analizar(_pel().leer_pelicula(Path(ruta).read_bytes()), CLICS[clave], _P(BASE_OD), modo_piso="automatico")
        assert r.ok and r.base == BASE_OD, (clave, r.estado)
        for capa in ("G", "B", "gris"):
            original = r.girada.capa(capa)
            piso = r.capas[capa].piso
            convertida = (200.0 - 100.0 * np.log10(piso / np.maximum(original.datos.astype(np.float64), VP_MINIMO))).astype(np.float32)
            capa_c = dataclasses.replace(original, datos=convertida)
            for i, eje in enumerate(EJES):
                produccion = getattr(r.capas[capa], eje)
                m = pm.medir_perfil(pm.perfil_central(capa_c, eje, _P(BASE_VP)), r.girada.cruce[i], 200.0, BASE_VP, _P(BASE_VP), r.bordes_luz_px[eje], r.geometria.reticulo_girado[i])
                atajo = pm.medir_perfil(pm.perfil_central(original, eje, _P(BASE_VP)), r.girada.cruce[i], piso, BASE_OD, _P(BASE_OD), r.bordes_luz_px[eje], r.geometria.reticulo_girado[i])
                assert produccion.ok and m.ok and atajo.ok, (clave, capa, eje, produccion.estado, m.estado, atajo.estado)
                salida[(clave, capa, eje)] = (produccion.fwhm_mm, m.fwhm_mm, produccion.bordes_rad_px, m.bordes_rad_px, atajo.fwhm_mm)
        del r
        gc.collect()
    yield salida
    salida.clear()
    gc.collect()


class TestLaImagenConvertidaEnPeliculasReales:
    """OD1-REV-PROD-01 / decision OD1-REV-D1 (opcion B). (c) del plan: la imagen convertida PIXEL A PIXEL a densidad optica da los mismos bordes que la base netOD a 0.02 mm o menos. Es cierto en la
    sintetica (arriba) y en las 18 combinaciones de tres peliculas reales (G, B y gris por dos ejes en EPSON008.TIF, EPSON001.TIF y EPSON007), SIN excepcion: la banda de 1 mm se promedia como esa imagen
    (la media de log10 por pixel). Antes de B la netOD tomaba el logaritmo del PROMEDIO LINEAL de la banda y una mota brillante dentro de ella acortaba el azul inplane de EPSON007 y de EPSON008.TIF casi 3 mm
    (96 mm contra 99): ese ATAJO se mide aqui mismo como control."""

    def test_la_netod_da_el_fwhm_y_los_dos_bordes_de_la_imagen_convertida_a_0_02_mm_en_las_18_combinaciones(self, contra_la_imagen_convertida):
        d = contra_la_imagen_convertida
        assert len(d) == len(PELICULAS_DE_LA_IMAGEN_CONVERTIDA) * 3 * 2 == 18
        for clave, (produccion, convertida, bordes_p, bordes_c, _) in d.items():
            assert abs(convertida - produccion) <= 0.02, (clave, produccion, convertida)
            for bp, bc in zip(bordes_p, bordes_c):
                assert abs(bc - bp) * TAM <= 0.02, (clave, bordes_p, bordes_c)

    @pytest.mark.parametrize("clave, ancho_de_la_imagen_convertida", [("EPSON007", 98.78), ("EPSON008_TIF", 99.03)])
    def test_la_mota_brillante_del_azul_inplane_no_acorta_el_ancho_fwhm_y_ambos_bordes_a_0_02_mm_de_la_convertida(self, contra_la_imagen_convertida, clave, ancho_de_la_imagen_convertida):
        produccion, convertida, bordes_p, bordes_c, atajo = contra_la_imagen_convertida[(clave, "B", "inplane")]
        assert convertida == pytest.approx(ancho_de_la_imagen_convertida, abs=0.011), "la imagen convertida (la ruta independiente) no cambio"
        assert produccion == pytest.approx(convertida, abs=0.02), (clave, produccion, convertida)
        assert len(bordes_p) == len(bordes_c) == 2
        for bp, bc in zip(bordes_p, bordes_c):
            assert abs(bc - bp) * TAM <= 0.02, (clave, "un borde coincide y el otro NO era el defecto de la mota", bordes_p, bordes_c)
        assert convertida - atajo > 2.5, f"{clave}: el control ya no discrimina: el atajo (promedio lineal) daba {atajo:.3f} mm y la convertida {convertida:.3f}; la mota se fue de la pelicula o del recorte"
        assert produccion - atajo > 2.5, "el motor sigue siendo el atajo"


def _media_de_los_logaritmos(filas):
    """El PROMEDIO DE LOS LOGARITMOS por pixel de una columna de la banda, con el piso de VP_MINIMO por pixel, de vuelta a niveles de 8 bits: lo que `perfil_central` debe dar en netOD (la verdad cerrada, en
    float64 y con `math`, que NO sale del codigo bajo prueba)."""
    return 10.0 ** (sum(math.log10(max(float(v), VP_MINIMO)) for v in filas) / len(filas))


class TestElPromedioDeLaBandaEsElDeLaImagenConvertida:
    """Decision OD1-REV-D1 (opcion B, de Opus, vetable por el fisico): con la netOD, la banda de 1 mm se promedia COMO LA IMAGEN CONVERTIDA PIXEL A PIXEL (la media de log10 por pixel, con el piso de VP_MINIMO
    por pixel); con el valor de pixel, la media aritmetica de siempre (la linea de HEAD, bit a bit). Se prueba CERRADO sobre una `CapaGirada` DISENADA: columnas donde la media aritmetica, la mediana y la media
    geometrica son tres numeros distintos (cada mutacion que cambia de agregador cae), un pixel en 0 (sin el piso de VP_MINIMO el logaritmo es -inf) y columnas al azar contra la formula en `math`."""
    CRUCE = (150.3, 100.7)                                    # (x, y): la banda de 1 mm del crossplane son las 24 filas de 89 a 112
    FILAS = slice(89, 113)
    ALTO, ANCHO = 300, 400
    COLUMNAS = {                                               # {columna: las 24 filas de la banda}
        60: [40.0] * 23 + [255.0],                             # una mota brillante: aritmetica 48.96, mediana 40.0, geometrica 43.2
        90: [100.0] * 23 + [0.0],                              # un pixel en 0 (el escaner lo recorto): sin el piso del logaritmo no existe la media
        120: [20.0] * 12 + [60.0] * 6 + [120.0] * 4 + [240.0] * 2,     # una distribucion asimetrica: aritmetica 65.0, mediana 40.0, geometrica 43.7 (una rampa lineal tendria mediana = media)
        150: [200.0] * 20 + [3.0, 5.0, 2.0, 0.2],              # varios pixeles bajo medio nivel: cada uno se piso por separado, no su promedio
        180: [120.0] * 24,                                     # el control: los tres agregadores coinciden
    }
    AL_AZAR = tuple(range(200, 233, 3))                       # 12 columnas con valores al azar entre 1 y 250
    PISO = 170.0

    def _datos(self):
        """La banda 0 (filas 89 a 112) lleva el patron disenado de cada columna; las bandas vecinas (-1: filas 66 a 88, +1: filas 113 a 136) llevan el mismo patron a otra escala (si la banda k se promediara
        con otra base que la banda 0, solo se vería con datos NO uniformes también en las vecinas)."""
        datos = np.full((self.ALTO, self.ANCHO), 150.0, dtype=np.float32)
        rng = np.random.default_rng(7)
        for j, filas in self.COLUMNAS.items():
            patron = np.asarray(filas, dtype=np.float32)
            datos[self.FILAS, j] = patron
            datos[66:89, j] = patron[:23] * np.float32(0.7)
            datos[113:137, j] = patron * np.float32(0.9)
        for j in self.AL_AZAR:
            datos[66:137, j] = rng.uniform(1.0, 250.0, 71).astype(np.float32)
        return datos

    def _capa(self, datos, *, inplane=False):
        pm = _pm()
        if inplane:
            return pm.CapaGirada(nombre="G", datos=np.ascontiguousarray(datos.T), validos=np.ones(datos.T.shape, bool), pelicula=np.ones(datos.T.shape, bool), origen=(0, 0), cruce=(self.CRUCE[1], self.CRUCE[0]), tam_mm=TAM)
        return pm.CapaGirada(nombre="G", datos=datos, validos=np.ones(datos.shape, bool), pelicula=np.ones(datos.shape, bool), origen=(0, 0), cruce=self.CRUCE, tam_mm=TAM)

    def test_la_banda_disenada_tiene_24_filas_y_los_tres_agregadores_son_distintos_donde_deben(self):
        """La premisa de la prueba: sin esto una mutacion de agregador podria pasar inadvertida."""
        datos = self._datos()
        perfil = _pm().perfil_central(self._capa(datos), "crossplane", _P(BASE_VP))
        assert perfil.filas_px == (89, 113) and perfil.n_filas == 24, "las columnas disenadas estan en las filas de la banda"
        for j in (60, 90, 120, 150):
            filas = [float(v) for v in datos[self.FILAS, j]]
            aritmetica, mediana, geometrica = float(np.mean(filas)), float(np.median(filas)), _media_de_los_logaritmos(filas)
            assert abs(aritmetica - mediana) > 0.5 and abs(aritmetica - geometrica) > 0.5 and abs(mediana - geometrica) > 0.5, (j, aritmetica, mediana, geometrica)
        for agregador in (np.mean, np.median):
            assert abs(agregador([float(v) for v in datos[self.FILAS, 180]]) - 120.0) < 1e-6 and abs(_media_de_los_logaritmos(datos[self.FILAS, 180]) - 120.0) < 1e-9

    def test_en_netod_la_banda_es_la_media_de_los_logaritmos_por_pixel_y_no_la_media_ni_la_mediana(self):
        datos = self._datos()
        valores = _pm().perfil_central(self._capa(datos), "crossplane", _P(BASE_OD), base=BASE_OD).valores
        for j in sorted(self.COLUMNAS) + list(self.AL_AZAR):
            esperado = _media_de_los_logaritmos(datos[self.FILAS, j])
            assert np.isfinite(valores[j]) and valores[j] == pytest.approx(esperado, rel=1e-12), (j, valores[j], esperado)

    def test_en_netod_la_densidad_optica_del_perfil_es_la_media_de_la_densidad_optica_de_cada_pixel(self):
        """log10(piso / valor del perfil) = la media de log10(piso / pixel): la netOD de la banda es el promedio de las netOD (la «imagen con la densidad optica aplicada» del fisico)."""
        datos = self._datos()
        valores = _pm().perfil_central(self._capa(datos), "crossplane", _P(BASE_OD), base=BASE_OD).valores
        for j in sorted(self.COLUMNAS) + list(self.AL_AZAR):
            media_de_las_netod = sum(od(self.PISO, float(v)) for v in datos[self.FILAS, j]) / 24
            assert math.log10(self.PISO / valores[j]) == pytest.approx(media_de_las_netod, abs=1e-12), (j,)

    def test_un_pixel_en_cero_no_rompe_la_banda_se_piso_en_medio_nivel_por_pixel(self):
        datos = self._datos()
        valores = _pm().perfil_central(self._capa(datos), "crossplane", _P(BASE_OD), base=BASE_OD).valores
        assert np.isfinite(valores[90]) and valores[90] == pytest.approx(100.0 ** (23 / 24) * VP_MINIMO ** (1 / 24), rel=1e-12), "el pixel en 0 cuenta como medio nivel"
        assert valores[150] == pytest.approx(10.0 ** ((20 * math.log10(200.0) + math.log10(3.0) + math.log10(5.0) + math.log10(2.0) + math.log10(VP_MINIMO)) / 24), rel=1e-12), "el 0.2 tambien se piso, cada pixel"
        assert np.isfinite(valores[40:361]).all()

    def test_en_valor_de_pixel_la_banda_es_la_media_aritmetica_de_siempre_bit_a_bit_y_es_la_base_por_omision_de_la_funcion(self):
        pm = _pm()
        datos = self._datos()
        capa = self._capa(datos)
        referencia = datos[self.FILAS].mean(axis=0, dtype=np.float64)                      # la linea de HEAD
        explicita = pm.perfil_central(capa, "crossplane", _P(BASE_VP), base=BASE_VP).valores
        sin_base = pm.perfil_central(capa, "crossplane", _P(BASE_VP)).valores
        assert np.array_equal(explicita[40:361], referencia[40:361]) and np.array_equal(sin_base[40:361], referencia[40:361]), "la media aritmetica, bit a bit"
        assert np.isnan(explicita[:24]).all() and np.isnan(explicita[-24:]).all(), "el margen del borde sigue siendo NaN"
        assert abs(explicita[60] - _media_de_los_logaritmos(datos[self.FILAS, 60])) > 0.5, "y en la mota difiere de la netOD: la prueba discrimina"

    def test_el_inplane_promedia_igual_que_el_crossplane_cada_columna_de_la_banda_con_su_base(self):
        pm = _pm()
        datos = self._datos()
        for base in (BASE_OD, BASE_VP):
            cruzado = pm.perfil_central(self._capa(datos), "crossplane", _P(base), base=base).valores
            vertical = pm.perfil_central(self._capa(datos, inplane=True), "inplane", _P(base), base=base).valores
            assert np.array_equal(np.isnan(cruzado), np.isnan(vertical)), (base, "el margen del borde (NaN) es el mismo")
            adentro = ~np.isnan(cruzado)
            assert adentro.sum() > 300 and np.allclose(cruzado[adentro], vertical[adentro], rtol=1e-13, atol=0), base          # no a nivel de bit: una vista transpuesta suma en otro orden

    def test_la_banda_k_del_barrido_se_promedia_con_la_misma_base_que_la_banda_cero(self):
        """`perfil_central(..., banda=k, base=)`: las bandas vecinas (k = +-1) tambien promedian en la base pedida."""
        pm = _pm()
        datos = self._datos()
        capa = self._capa(datos)
        for k in (-1, 1):
            perfil = pm.perfil_central(capa, "crossplane", _P(BASE_OD), banda=k, base=BASE_OD)
            primera, fin = perfil.filas_px
            assert perfil.banda == k and fin - primera in (23, 24) and (primera, fin) != (89, 113), "la banda vecina, no la central"
            distinguen = 0
            for j in (60, 90, 120, 200, 203):
                filas = datos[primera:fin, j]
                esperado = _media_de_los_logaritmos(filas)
                assert perfil.valores[j] == pytest.approx(esperado, rel=1e-12), (k, j)
                distinguen += abs(esperado - float(np.mean([float(v) for v in filas]))) > 0.5
            assert distinguen >= 2, (k, "la premisa: en la banda vecina la media aritmetica y la de los logaritmos deben ser distintas en al menos dos columnas")

    def test_una_base_que_no_existe_es_un_error_tambien_en_perfil_central(self):
        with pytest.raises(ValueError):
            _pm().perfil_central(self._capa(self._datos()), "crossplane", _P(BASE_OD), base="densidad")

    def test_la_firma_de_perfil_central_gana_base_y_su_valor_por_omision_es_el_de_hoy(self):
        import inspect
        pm = _pm()
        parametros = inspect.signature(pm.perfil_central).parameters
        assert list(parametros)[:5] == ["capa", "eje", "P", "banda", "base"]
        assert parametros["banda"].default == 0 and parametros["base"].default == pm.BASE_VALOR_DE_PIXEL == BASE_VP, "todo parametro nuevo lleva un valor por defecto que reproduce la conducta de hoy"


def _llamadas_de_produccion(nombre):
    """[(ruta relativa, funcion que contiene la llamada, nodo Call)] de toda llamada a `nombre` (suelta o como atributo) en el codigo de PRODUCCION (nada de tests ni de entornos)."""
    excluidos = {"tests", ".venv", "venv", "build", "dist", "__pycache__", ".git", "node_modules", ".pytest_cache"}
    encontradas = []
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in excluidos]
        for archivo in archivos:
            if not archivo.endswith(".py"):
                continue
            ruta = Path(carpeta) / archivo
            fuente = ruta.read_text(encoding="utf-8", errors="replace")
            if nombre not in fuente:
                continue
            arbol = ast.parse(fuente)
            contenedora = {}
            for f in ast.walk(arbol):
                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for hijo in ast.walk(f):
                        contenedora[id(hijo)] = f.name
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Call) and ((isinstance(nodo.func, ast.Name) and nodo.func.id == nombre) or (isinstance(nodo.func, ast.Attribute) and nodo.func.attr == nombre)):
                    encontradas.append((str(ruta.relative_to(RAIZ)).replace(os.sep, "/"), contenedora.get(id(nodo), "<modulo>"), nodo))
    return encontradas


class TestTodaLlamadaDeProduccionAPerfilCentralPasaLaBase:
    """Tripwire por AST (decision OD1-REV-D1): un llamador que olvide `base=` mediria la banda con el promedio de valor de pixel mientras `medir_perfil` normaliza en netOD: la mezcla que B cierra y que
    ninguna prueba de numeros veria si ese llamador no estuviera en la ruta de la prueba."""

    def test_el_censo_encuentra_a_los_dos_llamadores_de_verdad(self):
        llamadas = _llamadas_de_produccion("perfil_central")
        funciones = {(ruta, f) for ruta, f, _ in llamadas}
        assert ("analisisImagenes/placa_mensual.py", "_medir_la_capa") in funciones and ("analisisImagenes/placa_mensual.py", "_banda_del_barrido") in funciones, sorted(funciones)

    def test_cada_llamada_pasa_base_como_palabra_clave_y_es_la_base_del_analisis(self):
        for ruta, funcion, nodo in _llamadas_de_produccion("perfil_central"):
            claves = {k.arg: k.value for k in nodo.keywords}
            assert "base" in claves, f"{ruta}::{funcion} (linea {nodo.lineno}) llama a `perfil_central` sin `base=`: mediria la banda en valor de pixel con una base netOD"
            valor = claves["base"]
            assert (isinstance(valor, ast.Name) and valor.id == "base") or (isinstance(valor, ast.Attribute) and valor.attr == "base"), \
                f"{ruta}::{funcion} (linea {nodo.lineno}) pasa a `base=` algo que no es la base del analisis (`base` o `resultado.base`): {ast.unparse(valor)}"

    def test_la_banda_cero_del_barrido_tiene_el_mismo_perfil_que_el_corte_central_valor_por_valor(self, analisis_od):
        """No solo el FWHM: los `valores` del perfil de la banda 0 del barrido son los del perfil del corte central, en netOD (si uno de los dos llamadores olvidara la base, uno promediaria en pixel)."""
        pm = _pm()
        assert analisis_od.base == BASE_OD
        barrido = pm.barrido(analisis_od)
        for capa in ("G", "B", "gris"):
            for eje in EJES:
                central = getattr(analisis_od.capas[capa], eje).perfil.valores
                cero = barrido.ejes[eje].capas[capa].central.medida.perfil.valores
                assert np.array_equal(central, cero, equal_nan=True), (capa, eje)

    def test_el_corte_central_de_analizar_promedia_en_la_base_del_analisis_no_en_la_de_pixel(self, analisis_od):
        """Las `valores` del corte central del analisis netOD son los de `perfil_central(..., base=netOD)` y NO los de la media aritmetica (en la sintetica la banda tiene ruido: difieren)."""
        pm = _pm()
        for capa in ("G", "gris"):
            for eje in EJES:
                central = getattr(analisis_od.capas[capa], eje).perfil.valores
                en_od = pm.perfil_central(analisis_od.girada.capa(capa), eje, _P(BASE_OD), base=BASE_OD).valores
                en_vp = pm.perfil_central(analisis_od.girada.capa(capa), eje, _P(BASE_VP), base=BASE_VP).valores
                assert np.array_equal(central, en_od, equal_nan=True), (capa, eje)
                assert not np.array_equal(central, en_vp, equal_nan=True), (capa, eje, "el corte central quedo en la media aritmetica")


class TestElBarridoYElRestoUsanLaBaseDelAnalisis:
    def test_la_banda_cero_del_barrido_es_el_corte_central_en_netod(self, analisis_od):
        pm = _pm()
        assert analisis_od.base == BASE_OD, "el analisis es netOD: el barrido que sigue lo es"
        barrido = pm.barrido(analisis_od)
        assert barrido.ok
        for capa in ("G", "B", "gris"):
            for eje in EJES:
                central = barrido.ejes[eje].capas[capa].central
                assert central is not None and central.fwhm_mm == getattr(analisis_od.capas[capa], eje).fwhm_mm, (capa, eje)

    def test_el_barrido_de_un_analisis_en_pixel_mide_en_pixel(self, sintetica):
        """El barrido usa `resultado.base`: con una base de pixel la banda 0 es el corte central de pixel (y distinto del de netOD)."""
        pm = _pm()
        vp = pm.analizar(sintetica.pelicula, sintetica.puntos, _P(BASE_VP), modo_piso="automatico")
        b = pm.barrido(vp)
        assert b.ejes["crossplane"].capas["G"].central.fwhm_mm == vp.capas["G"].crossplane.fwhm_mm

    def test_el_rojo_recortado_no_se_barre_como_medible_en_netod(self, analisis_od):
        """El rojo de la sintetica llega a 1 nivel (como el de las peliculas reales a 800 UM): en netOD esta recortado, y el barrido, que usa la misma `medir_perfil`, no mide ni una banda suya."""
        pm = _pm()
        assert analisis_od.base == BASE_OD
        for eje in EJES:
            assert not getattr(analisis_od.capas["R"], eje).ok and pm.MOTIVO_MESETA_RECORTADA in getattr(analisis_od.capas["R"], eje).estado
        barrido = pm.barrido(analisis_od)
        for eje in EJES:
            rojo = barrido.ejes[eje].capas["R"]
            assert not rojo.ok and rojo.estadistica.n_medibles == 0 and all(not b.ok for b in rojo.bandas), (eje, rojo.estado)
            assert barrido.ejes[eje].capas["G"].ok, "las otras capas si se barren"


class TestAnalizarLeeLaBaseDelParametro:
    def test_el_parametro_manda_y_el_resultado_la_dice(self, sintetica):
        pm = _pm()
        for base in (BASE_OD, BASE_VP):
            r = pm.analizar(sintetica.pelicula, sintetica.puntos, _P(base), modo_piso="automatico")
            assert r.base == base and r.parametros["base_de_la_medida"] == base and r.como_dict()["base"] == base
            del r
            gc.collect()

    def test_un_registro_sin_el_parametro_se_mide_como_se_midio_en_valor_de_pixel(self, sintetica):
        pm = _pm()
        P = _P()
        del P["base_de_la_medida"]
        r = pm.analizar(sintetica.pelicula, sintetica.puntos, P, modo_piso="automatico")
        assert r.base == BASE_VP and r.parametros["base_de_la_medida"] == BASE_VP, "los parametros dicen la base con que SE MIDIO"
        igual = pm.analizar(sintetica.pelicula, sintetica.puntos, _P(BASE_VP), modo_piso="automatico")
        assert pm.valores_medidos(r, "G") == pm.valores_medidos(igual, "G")

    def test_una_base_que_no_existe_lanza_value_error_antes_de_medir(self, sintetica):
        pm = _pm()
        with pytest.raises(ValueError) as e:
            pm.analizar(sintetica.pelicula, sintetica.puntos, _P("dosis absoluta"))
        assert BASE_OD in str(e.value)

    def test_los_puntos_que_no_forman_el_campo_conservan_la_base_pedida(self, sintetica):
        pm = _pm()
        r = pm.analizar(sintetica.pelicula, [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)], _P(BASE_OD), modo_piso="automatico")
        assert not r.ok and r.base == BASE_OD and r.parametros["base_de_la_medida"] == BASE_OD
        assert pm.barrido(r).estado.startswith("no medible")

    def test_con_la_base_de_pixel_y_sin_referencia_el_resultado_es_el_de_siempre(self, sintetica):
        """Lo que fija el diferencial del anexo, en pequeno: pixel + sin referencia + modo automatico = lo que HEAD medía (el FWHM del verde de la sintetica con el piso de las esquinas)."""
        pm = _pm()
        r = pm.analizar(sintetica.pelicula, sintetica.puntos, _P(BASE_VP))
        assert r.piso.modo == "automatico" and r.capas["G"].crossplane.ok
        assert r.capas["G"].crossplane.fwhm_mm == pytest.approx(101.036, abs=0.3), "la verdad del generador en el verde (valor de pixel)"


# ===================================================================================================== (g) modo_efectivo

class TestModoEfectivo:
    def test_la_virgen_si_hay_referencia_y_las_esquinas_si_no(self):
        pel = _pel()
        ref = object()
        assert pel.modo_efectivo(None, ref) == "virgen"
        assert pel.modo_efectivo(None, None) == "automatico"
        assert pel.modo_efectivo(None) == "automatico"

    @pytest.mark.parametrize("modo", ["automatico", "punto_manual", "virgen"])
    @pytest.mark.parametrize("referencia", [None, object()])
    def test_un_modo_pedido_se_respeta_aunque_la_referencia_diga_otra_cosa(self, modo, referencia):
        assert _pel().modo_efectivo(modo, referencia) == modo

    def test_un_punto_marcado_sin_modo_pide_el_punto_manual_y_la_virgen_ya_no_lo_pisa(self):
        pel = _pel()
        assert pel.modo_efectivo(None, object(), (10.0, 20.0)) == "punto_manual"
        assert pel.modo_efectivo(None, None, (10.0, 20.0)) == "punto_manual"

    def test_la_virgen_sin_referencia_sigue_siendo_no_medible_nunca_cae_a_las_esquinas(self, sintetica):
        pel = _pel()
        campo = [sintetica.puntos[i] for i in range(4)]
        piso = pel.piso_de_pelicula(sintetica.pelicula, campo, _P(), modo="virgen")
        assert piso.estado.startswith("no medible") and "no hay película virgen de referencia" in piso.estado and piso.origen == "virgen"

    def test_piso_de_pelicula_y_analizar_aplican_la_regla(self, sintetica, escaneo_virgen):
        """Sin modo pedido: con referencia el piso es virgen, sin ella de esquinas; con un modo pedido, ese. Es la MISMA regla en las dos funciones."""
        pel, pm = _pel(), _pm()
        campo = [sintetica.puntos[i] for i in range(4)]
        ref = escaneo_virgen.referencia
        piso_virgen = pel.piso_de_pelicula(sintetica.pelicula, campo, _P(), referencia_virgen=ref)
        assert piso_virgen.origen == "virgen" and piso_virgen.estado == "ok", piso_virgen.estado
        assert all(piso_virgen.capas[c].mediana == ref.valor(c) for c in TODAS), "el piso de cada capa ES el valor de la referencia (su media)"
        assert pel.piso_de_pelicula(sintetica.pelicula, campo, _P()).origen == "automatico"
        assert pel.piso_de_pelicula(sintetica.pelicula, campo, _P(), modo="automatico", referencia_virgen=ref).origen == "automatico"
        r = pm.analizar(sintetica.pelicula, sintetica.puntos, _P(), referencia_virgen=ref)
        assert r.piso.modo == "virgen" and r.piso.referencia is ref
        del r
        gc.collect()
        r = pm.analizar(sintetica.pelicula, sintetica.puntos, _P())
        assert r.piso.modo == "automatico"
        del r
        gc.collect()

    def test_la_referencia_invalida_no_se_adapta_en_silencio(self, sintetica):
        """Con una referencia presente pero «no valida», el modo efectivo es virgen y el piso queda «no medible»: nunca cae sola a las esquinas (V7)."""
        pel = _pel()
        campo = [sintetica.puntos[i] for i in range(4)]
        mala = pel.piso_de_pelicula_virgen(b"esto no es una imagen", _P(), "mala.tif", fecha_calculo="2026-10-21")
        assert mala.estado.startswith("no válida")
        piso = pel.piso_de_pelicula(sintetica.pelicula, campo, _P(), referencia_virgen=mala)
        assert piso.origen == "virgen" and piso.estado.startswith("no medible")


# ===================================================================================================== (f) la pelicula virgen real

def _ruta_real(nombre):
    """La ruta de una pelicula real DECLARADA en `tests/_corpus.py` (se pide por el nombre de su archivo). Salta (HI-0) si la carpeta de peliculas no la tiene; la regla de PR.0 FALLA si la carpeta existe y a la
    declarada le falta el archivo (OD1-REV-PRU-02). Una pelicula que no esta declarada es un error de la prueba, no un salto: no habria quien vigilara que existe."""
    claves = [clave for clave, archivo in _corpus.peliculas_vigiladas_por_pr0().items() if archivo == nombre]
    assert len(claves) == 1, f"{nombre} no esta declarada en tests/_corpus.py (PELICULAS_VIRGENES o los registros de peliculas): declarela para que PR.0 la vigile"
    ruta = _corpus.pelicula(claves[0])
    if ruta is None:
        pytest.skip(f"HI-0: {nombre} no esta en {_corpus.PELICULAS_RAIZ}")
    return Path(ruta)


# Lo medido el 21-10 (logs/OD/od1_v2_media_virgen_zona.log y od1_v2_virgen_tamanos.log): la MEDIA por capa de la zona de A.3 sin lo que se aparta mas de 25 niveles de la mediana, y la tabla de
# uniformidad tipo Catphan (media del centro, mayor diferencia con el centro en %, ruido = desviacion del centro en niveles) de R, G y B.
EPSON179 = {"media": {"R": 152.12, "G": 194.11, "B": 86.77, "gris": 169.30},
            "uniformidad": {"R": (153.10, 1.07, 1.25), "G": (194.93, 0.59, 0.66), "B": (88.50, 5.11, 1.60)}}
PIEZAS = {          # nombre -> (media R G B gris, uniformidad {capa: (centro, %, ruido)})
    "centro": ((152.39, 194.51, 87.64, 169.72), {"R": (153.11, 1.48, 1.24), "G": (194.94, 0.88, 0.66), "B": (88.50, 3.56, 1.60)}),
    "izquierda": ((150.55, 193.04, 83.99, 167.86), {"R": (151.13, 1.21, 1.75), "G": (193.85, 1.12, 1.28), "B": (84.64, 4.44, 2.28)}),
    "derecha": ((153.56, 195.21, 89.25, 170.68), {"R": (153.09, 0.44, 1.36), "G": (195.00, 0.16, 0.78), "B": (88.93, 0.60, 1.62)}),
    "hoja": ((152.22, 194.17, 86.86, 169.38), {"R": (153.11, 1.26, 1.24), "G": (194.94, 0.56, 0.66), "B": (88.50, 4.38, 1.60)}),
}


@pytest.fixture(scope="module")
def virgen_179():
    """La referencia de EPSON179.TIF medida con el codigo de hoy, una vez por modulo (sus arreglos no se guardan: la referencia es solo numeros)."""
    datos = _ruta_real("EPSON179.TIF").read_bytes()
    ref = _pel().piso_de_pelicula_virgen(datos, _P(), "EPSON179.TIF", fecha_calculo="2026-10-21")
    yield types.SimpleNamespace(ref=ref, datos=datos)
    gc.collect()


PELICULA_SIN_DECLARAR = "PELICULA_QUE_NADIE_DECLARO.TIF"            # una constante y no un literal en la llamada: el censo por AST de PR.0 solo mira los literales que piden una pelicula de verdad


def test_una_pelicula_real_sin_declarar_es_un_error_de_la_prueba_y_no_un_salto():
    """OD1-REV-PRU-02: `_ruta_real` de un archivo que el corpus no declara FALLA (nadie vigilaria que existe) en vez de saltarse como una declarada que falta."""
    try:
        _ruta_real(PELICULA_SIN_DECLARAR)
    except AssertionError as error:
        assert "no esta declarada" in str(error)
    except BaseException as otra:                  # un salto (`pytest.skip`) no es BaseException de AssertionError: pytest lo daria por una prueba saltada y no por una que falla
        pytest.fail(f"una pelicula sin declarar tiene que FALLAR con un AssertionError, no {type(otra).__name__}", pytrace=False)
    else:
        pytest.fail("una pelicula sin declarar tiene que fallar", pytrace=False)


class TestLaPeliculaVirgenReal:
    def test_epson179_se_acepta_y_su_valor_es_la_media_por_capa_a_0_01(self, virgen_179):
        ref = virgen_179.ref
        assert ref.estado == "ok", ref.estado
        for capa, esperado in EPSON179["media"].items():
            assert ref.valor(capa) == pytest.approx(esperado, abs=0.011), (capa, ref.valor(capa))

    def test_el_valor_es_la_media_y_no_la_mediana(self, virgen_179):
        """La mediana de la zona (la que mira el rango) del azul es 88 y su media 86.77: si el valor fuera la mediana, el piso azul subiria 1.2 niveles (0.17 mm de FWHM)."""
        ref = virgen_179.ref
        assert ref.valor("B") < ref.capas["B"].mediana - 0.5
        assert ref.capas["B"].mediana == pytest.approx(88.0, abs=0.6)

    def test_c3_c5_y_c6_son_avisos_y_ninguna_prueba_rechaza(self, virgen_179):
        resultados = {p.nombre: p.resultado for p in virgen_179.ref.pruebas}
        assert "rechazo" not in resultados.values(), resultados
        assert resultados["C5 uniformidad"] == "aviso" and resultados["C5 gradiente"] == "aviso" and resultados["C6 motas"] == "aviso", resultados
        assert resultados["C1 cadena"] == "ok" and resultados["C2 zona"] == "ok" and resultados["rango"] == "ok"

    def test_la_tabla_de_uniformidad_y_ruido_es_la_del_pre_vuelo(self, virgen_179):
        u = virgen_179.ref.uniformidad
        assert u["cabe"] is True and u["lado_mm"] == 10.0 and set(u["regiones"]) == {"centro", "arriba", "abajo", "izquierda", "derecha"}
        for capa, (centro, pct, ruido) in EPSON179["uniformidad"].items():
            fila = u["capas"][capa]
            assert fila["centro"] == pytest.approx(centro, abs=0.011), capa
            assert fila["uniformidad_pct"] == pytest.approx(pct, abs=0.011), capa
            assert fila["ruido"] == pytest.approx(ruido, abs=0.011), capa
        assert set(u["capas"]) == set(TODAS) and np.isfinite(u["capas"]["gris"]["uniformidad_pct"]) and u["capas"]["gris"]["ruido"] > 0

    def test_la_uniformidad_es_la_mayor_diferencia_con_el_centro_en_porcentaje(self, virgen_179):
        for capa in TODAS:
            fila = virgen_179.ref.uniformidad["capas"][capa]
            medias = fila["regiones"]
            assert set(medias) == {"centro", "arriba", "abajo", "izquierda", "derecha"}
            peor = max(abs(medias[r] - medias["centro"]) for r in ("arriba", "abajo", "izquierda", "derecha")) / medias["centro"] * 100.0
            assert fila["uniformidad_pct"] == pytest.approx(peor, abs=1e-9) and fila["centro"] == medias["centro"]

    def test_el_gradiente_lateral_de_c5_va_en_la_misma_tabla(self, virgen_179):
        """C5 midio 2.2 / 1.3 / 6.7 % por 10 cm en x (rojo, verde, azul): el numero se guarda, no solo el texto."""
        u = virgen_179.ref.uniformidad["capas"]
        assert abs(u["R"]["gradiente_x_pct_por_10cm"]) == pytest.approx(2.23, abs=0.05)
        assert abs(u["G"]["gradiente_x_pct_por_10cm"]) == pytest.approx(1.29, abs=0.05)
        assert abs(u["B"]["gradiente_x_pct_por_10cm"]) == pytest.approx(6.66, abs=0.05)
        assert u["gris"]["gradiente_x_pct_por_10cm"] is None, "C5 no juzga el gris"

    def test_la_referencia_guarda_donde_estaba_la_pelicula_en_la_pagina(self, virgen_179):
        """La caja de la pelicula en la pagina (mm): EPSON179 es una hoja de 210.9 x 279.1 mm en una pagina de 215.9 x 279.4 (logs/OD/od1_v2_virgen_tamanos.log)."""
        r = virgen_179.ref.region
        assert r["pelicula_mm"]["ancho"] == pytest.approx(210.9, abs=0.15) and r["pelicula_mm"]["alto"] == pytest.approx(279.1, abs=0.15)
        assert r["pelicula_mm"]["x"] == pytest.approx(0.0, abs=0.15) and r["pelicula_mm"]["y"] == pytest.approx(0.3, abs=0.15)
        assert r["pagina_mm"]["ancho"] == pytest.approx(215.9, abs=0.1) and r["pagina_mm"]["alto"] == pytest.approx(279.4, abs=0.1)
        texto = _dib().texto_de_la_caja_de_la_pelicula(virgen_179.ref)
        assert "210.9" in texto and "279.1" in texto and "215.9" in texto and "279.4" in texto and sin_simbolos(texto), texto

    def test_epson178_se_rechaza_solo_por_el_rango(self):
        """178 (ajustes automaticos del escaner): R 193, G 240, gris 212, fuera del rango de una pelicula sin irradiar. Su recorte, su ruido y su uniformidad son avisos, no rechazos."""
        ref = _pel().piso_de_pelicula_virgen(_ruta_real("EPSON178.TIF").read_bytes(), _P(), "EPSON178.TIF", fecha_calculo="2026-10-21")
        rechazos = {p.nombre for p in ref.pruebas if p.resultado == "rechazo"}
        assert rechazos == {"rango"}, {p.nombre: p.resultado for p in ref.pruebas}
        assert ref.estado.startswith("no válida: fuera del rango esperado de una película sin irradiar")
        for texto in ("rojo 193", "verde 240", "gris 212"):
            assert texto in ref.estado
        assert {p.nombre: p.resultado for p in ref.pruebas}["C3 recorte"] == "aviso"
        assert all(c.mediana is None for c in ref.capas.values()), "una virgen no valida no da ningun piso"


def _virgen_con_tinta(semilla, lado_mm):
    """La virgen sintetica (la de `escaneo_virgen`) y la MISMA con un cuadrado de TINTA (un tono mucho mas oscuro en las tres capas) de `lado_mm` en el centro de la pelicula, dentro de la zona medida:
    (bytes de la limpia, bytes de la manchada)."""
    calibracion = dict(gen.CALIB, meseta_bgr=gen.CALIB["virgen_bgr"], fondo_escaner=255.0)
    arreglo, _ = gen.generar_arreglo(variante="A", theta_deg=0.0, bits=8, dpi=600, tinta=False, calib=calibracion, seed=semilla)
    arreglo = np.array(arreglo)
    arreglo[arreglo.min(axis=2) >= 235] = 255
    ys, xs = np.nonzero(arreglo.min(axis=2) < 235)
    cy, cx, mitad = int(ys.mean()), int(xs.mean()), int(round(lado_mm / TAM)) // 2
    limpia = gen.codificar(arreglo, "tiff", 600)
    arreglo[cy - mitad:cy + mitad, cx - mitad:cx + mitad] = 40
    return limpia, gen.codificar(arreglo, "tiff", 600)


class TestLaMediaDeLaVirgenNoCuentaLaTinta:
    def test_la_media_no_cuenta_la_tinta_ni_lo_que_se_aparta_mas_de_delta_tinta_de_la_mediana(self):
        """El valor de la virgen es la media SIN lo que se aparta mas de `delta_tinta` (25) niveles de la mediana de su capa. Un cuadrado de tinta de 8 x 8 mm (0.5 % de la zona, a 40 niveles: 110 a 150 niveles
        bajo la mediana) sacaria la media de la limpia mas de 0.5 niveles si se contara; sin contarla queda donde estaba."""
        pel = _pel()
        limpia, manchada = _virgen_con_tinta(1, 8.0)
        a = pel.piso_de_pelicula_virgen(limpia, _P(), "limpia.tif", fecha_calculo="2026-10-21")
        b = pel.piso_de_pelicula_virgen(manchada, _P(), "manchada.tif", fecha_calculo="2026-10-21")
        assert a.estado == "ok" and b.estado == "ok", (a.estado, b.estado)
        assert {p.nombre: p.resultado for p in b.pruebas}["C6 motas"] in ("ok", "aviso"), "la tinta no rechaza la virgen: se ve, a lo sumo, como aviso"
        for capa in TODAS:
            assert b.valor(capa) == pytest.approx(a.valor(capa), abs=0.15), (capa, a.valor(capa), b.valor(capa))
            assert b.capas[capa].mediana == pytest.approx(a.capas[capa].mediana, abs=1.0), "la mediana (la que mira el rango) tampoco se mueve"


def _a_tiff(bgra):
    buf = io.BytesIO()
    Image.fromarray(cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA), "RGBA").save(buf, format="TIFF", dpi=(600.0, 600.0), compression="tiff_lzw")
    return buf.getvalue()


def _en_carta(pieza):
    pag = np.full((6600, 5100, 4), 255, np.uint8)
    h, w = pieza.shape[:2]
    y0, x0 = (6600 - h) // 2, (5100 - w) // 2
    pag[y0:y0 + h, x0:x0 + w] = pieza
    return pag


@pytest.fixture(scope="module")
def piezas_de_179():
    """Las cuatro piezas del pedido del fisico (10 x 10 cm del centro, del borde izquierdo y del derecho sobre una carta blanca, y la hoja sin fondo), armadas EN MEMORIA con trozos reales de
    EPSON179 (ningun archivo nuevo en el corpus): {nombre: bytes del TIFF}. Se sueltan al terminar el modulo."""
    original = cv2.imread(str(_ruta_real("EPSON179.TIF")), cv2.IMREAD_UNCHANGED)
    if original.shape[2] == 3:
        original = cv2.cvtColor(original, cv2.COLOR_BGR2BGRA)
    pelicula = (original[:, :, :3].min(axis=2) < 235).astype(np.uint8)
    _, _, st, _ = cv2.connectedComponentsWithStats(pelicula, 8)
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = (int(v) for v in st[k, :4])
    del pelicula
    px_mm = 600.0 / 25.4
    L, cy, margen = int(round(100 * px_mm)), y + h // 2, int(round(8 * px_mm))
    salida = {}
    for nombre, x0 in (("centro", x + w // 2 - L // 2), ("izquierda", x + margen), ("derecha", x + w - margen - L)):
        pieza = original[cy - L // 2: cy - L // 2 + L, x0: x0 + L].copy()
        pieza[:, :, 3] = 255
        salida[nombre] = _a_tiff(_en_carta(pieza))
        del pieza
    hoja = original[y + margen: y + h - margen, x + margen: x + w - margen].copy()
    hoja[:, :, 3] = 255
    salida["hoja"] = _a_tiff(hoja)
    del hoja, original
    gc.collect()
    yield salida
    salida.clear()
    gc.collect()


class TestElTamanoDeLaPeliculaVirgen:
    @pytest.mark.parametrize("nombre", ["centro", "izquierda", "derecha", "hoja"])
    def test_las_cuatro_se_aceptan_con_su_media_y_sus_cinco_regiones(self, piezas_de_179, nombre):
        ref = _pel().piso_de_pelicula_virgen(piezas_de_179[nombre], _P(), f"{nombre}.tif", fecha_calculo="2026-10-21")
        assert ref.estado == "ok", (nombre, ref.estado, [(p.nombre, p.resultado) for p in ref.pruebas])
        medias, uniformidad = PIEZAS[nombre]
        for capa, esperado in zip(TODAS, medias):
            assert ref.valor(capa) == pytest.approx(esperado, abs=0.011), (nombre, capa)
        u = ref.uniformidad
        assert u["cabe"] is True and all(u["regiones"][r]["caja"] is not None for r in ("centro", "arriba", "abajo", "izquierda", "derecha")), "las cinco regiones caben"
        for capa, (centro, pct, ruido) in uniformidad.items():
            fila = u["capas"][capa]
            assert (fila["centro"], fila["uniformidad_pct"], fila["ruido"]) == pytest.approx((centro, pct, ruido), abs=0.011), (nombre, capa)
        resultado = {p.nombre: (p.resultado, p.texto) for p in ref.pruebas}
        assert resultado["C6 motas"][0] in ("ok", "aviso"), "la pieza de 10 x 10 del centro tiene motas en el 2.14 % y ya no se rechaza"
        if nombre == "hoja":
            assert resultado["C3 fondo"] == ("ok", "no se ve fondo del escáner; no se juzga")
        else:
            assert resultado["C3 fondo"][0] == "ok" and resultado["C3 fondo"][1].startswith("el 100.00 % del fondo")

    def test_el_lugar_del_escaner_mueve_el_piso_y_la_referencia_lo_dice(self, piezas_de_179):
        """Una pieza de 10 x 10 da +-1.1 niveles en el verde y +-2.8 en el azul segun donde se ponga (la respuesta lateral del escaner): se ve y se guarda, no se corrige."""
        izq = _pel().piso_de_pelicula_virgen(piezas_de_179["izquierda"], _P(), "i.tif", fecha_calculo="2026-10-21")
        der = _pel().piso_de_pelicula_virgen(piezas_de_179["derecha"], _P(), "d.tif", fecha_calculo="2026-10-21")
        assert der.valor("B") - izq.valor("B") > 4.0 and der.valor("G") - izq.valor("G") > 1.5
        for ref in (izq, der):
            region = ref.region
            assert region["pelicula_mm"]["ancho"] == pytest.approx(100.0, abs=0.3) and region["pagina_mm"]["alto"] == pytest.approx(279.4, abs=0.1), "dice donde estaba la pieza y la pagina"


def _tiff_rgb(pieza, pagina=3000):
    """Una pieza RGB de 8 bits (alto x ancho x 3) pegada a 300 px del borde de una pagina blanca cuadrada, como TIFF a 600 ppp: la verdad conocida de cada prueba es lo que se puso en la pieza."""
    arreglo = np.full((pagina, pagina, 3), 255, np.uint8)
    alto, ancho = pieza.shape[:2]
    arreglo[300:300 + alto, 300:300 + ancho] = pieza
    buf = io.BytesIO()
    Image.fromarray(arreglo).save(buf, format="TIFF", dpi=(600, 600))
    return buf.getvalue()


# ===================================================================================================== ronda 1 de revision: la virgen con un nivel en cero y el signo de su gradiente

class TestLaVirgenNuncaLanzaPorElContenido:
    """OD1-REV-PROD-02. `piso_de_pelicula_virgen` promete NO lanzar por el contenido. Con C3 convertida en aviso (OD.1) un escaneo con una capa en 0 ya no se rechaza al empezar y llegaba a dividir entre el
    nivel de esa capa con floats de Python (`ZeroDivisionError` en el gradiente de C5 y en la uniformidad; en HEAD esa division era de numpy y daba nan). Un nivel en 0 no tiene respecto de que medir un porcentaje:
    la referencia queda «no valida» por el rango (un 0 esta fuera de lo esperado en una pelicula sin irradiar), su tabla dice «sin medir» para esa capa y nunca aparece un numero inventado ni un nan."""
    CASOS = [("negra", 2400, (0, 0, 0), {"R", "G", "B", "gris"}),
             ("rojo en 0, 10 cm", 2400, (0, 190, 85), {"R"}),             # recorre el gradiente de C5 (la zona mide mas de 60 mm)
             ("rojo en 0, 5 cm", 1180, (0, 190, 85), {"R"}),              # solo la uniformidad (la zona no llega a los 60 mm del gradiente)
             ("verde en 0, 10 cm", 2400, (150, 0, 85), {"G"}),
             ("azul en 0, 10 cm", 2400, (150, 190, 0), {"B"})]

    @pytest.mark.parametrize("nombre, lado, rgb, en_cero", CASOS, ids=[c[0] for c in CASOS])
    def test_una_capa_en_cero_no_lanza_la_referencia_no_es_valida_por_el_rango_y_su_tabla_dice_sin_medir(self, nombre, lado, rgb, en_cero):
        ref = _pel().piso_de_pelicula_virgen(_tiff_rgb(np.full((lado, lado, 3), rgb, np.uint8)), _P(), "x.tif", fecha_calculo="2026-10-22")
        assert ref.estado.startswith("no válida: fuera del rango esperado de una película sin irradiar"), ref.estado
        assert all(c.mediana is None for c in ref.capas.values()), "una virgen no valida no da ningun piso"
        tabla = ref.uniformidad
        assert tabla is not None and tabla["cabe"] is True, "la tabla se conserva: es lo que le explica al fisico por que no sirve"
        for capa in TODAS:
            fila = tabla["capas"][capa]
            if capa in en_cero:
                assert fila["centro"] == 0.0 and fila["ruido"] == 0.0, capa
                assert fila["uniformidad_pct"] is None, f"{capa}: la uniformidad es la diferencia con el centro EN % del centro, y el centro vale 0"
                assert fila["gradiente_x_pct_por_10cm"] is None and fila["gradiente_y_pct_por_10cm"] is None, capa
            else:
                assert fila["uniformidad_pct"] == pytest.approx(0.0, abs=1e-9), f"{capa}: una capa que no esta en cero se mide como siempre"
        for prueba in ref.pruebas:
            assert not re.search(r"\b(nan|inf)\b", prueba.texto.lower()), f"{prueba.nombre}: {prueba.texto}"
        filas = _dib().filas_de_la_uniformidad(ref)
        assert all(sin_simbolos(celda) and not re.search(r"\b(nan|inf)\b", celda.lower()) for fila in filas for celda in fila)


class TestElGradienteLateralLlevaSuSigno:
    """OD1-REV-PRU-03. C5 reporta el gradiente lateral CON SIGNO (positivo = mas clara hacia la derecha o hacia abajo): es lo unico que A.3, que lo daba en valor absoluto, cambio. EPSON179 tiene signo positivo en
    R, G y B, asi que volver a `abs()` era invisible con los datos reales. Aqui la verdad conocida es una rampa lineal construida por la prueba, en las dos direcciones y con los dos sentidos."""
    A = 0.0005                                     # 0.05 % del nivel por mm: 5 % por 10 cm
    BASE = np.array([150.0, 190.0, 85.0])
    LADO = 2400

    def _pieza(self, direccion, signo):
        rampa = 1.0 + signo * self.A * np.arange(self.LADO) * TAM
        factor = rampa[None, :, None] if direccion == "x" else rampa[:, None, None]
        return np.clip(np.rint(np.broadcast_to(self.BASE[None, None, :] * factor, (self.LADO, self.LADO, 3))), 0, 255).astype(np.uint8)

    @pytest.mark.parametrize("direccion", ["x", "y"])
    @pytest.mark.parametrize("signo", [+1, -1])
    def test_mas_clara_hacia_la_derecha_o_abajo_es_positivo_y_hacia_el_otro_lado_negativo(self, direccion, signo):
        ref = _pel().piso_de_pelicula_virgen(_tiff_rgb(self._pieza(direccion, signo)), _P(), "rampa.tif", fecha_calculo="2026-10-22")
        esperado = signo * 10000.0 * self.A / (1.0 + signo * self.A * (self.LADO * TAM) / 2.0)        # pendiente / nivel medio, en % por 10 cm: la formula cerrada de una rampa
        otra = "y" if direccion == "x" else "x"
        assert esperado * signo == pytest.approx(5.0, abs=0.2), "premisa: la rampa es de unos 5 % por 10 cm"
        for capa in ("R", "G", "B"):
            fila = ref.uniformidad["capas"][capa]
            assert fila[f"gradiente_{direccion}_pct_por_10cm"] == pytest.approx(esperado, abs=0.15), (capa, direccion, signo)
            assert abs(fila[f"gradiente_{otra}_pct_por_10cm"]) < 0.15, (capa, "la otra direccion no tiene rampa")
        assert ref.uniformidad["capas"]["gris"]["gradiente_x_pct_por_10cm"] is None, "C5 no juzga el gris"
        celda = _dib().filas_de_la_uniformidad(ref)[0][8 if direccion == "x" else 9]
        assert celda.startswith("+" if signo > 0 else "-") and float(celda) == pytest.approx(esperado, abs=0.15), f"la tabla dice el signo: {celda!r}"


class TestLaReferenciaVirgenViajaComoJson:
    """Su JSON sube de version (PV-2): trae la media de cada capa y la tabla de uniformidad y ruido. Una de la version anterior se rechaza con su motivo (no hay ninguna guardada)."""

    def test_la_version_es_pv_2_y_la_ida_y_vuelta_conserva_todo(self, escaneo_virgen):
        pel = _pel()
        ref = escaneo_virgen.referencia
        d = json_ida_y_vuelta(ref.como_dict())
        assert pel.VERSION_PISO_VIRGEN == "PV-2" and d["version"] == "PV-2" and ref.procedencia["version"] == "PV-2"
        assert all("media" in d["capas"][c] and d["capas"][c]["media"] == ref.valor(c) for c in TODAS) and d["uniformidad"]["cabe"] is True
        otra = pel.referencia_virgen_desde_dict(d)
        assert otra.como_dict() == ref.como_dict() and otra.uniformidad == ref.uniformidad and otra.valor("G") == ref.valor("G")

    def test_una_referencia_sin_la_media_o_sin_la_uniformidad_esta_danada(self, escaneo_virgen):
        pel = _pel()
        d = json_ida_y_vuelta(escaneo_virgen.referencia.como_dict())
        sin_media = copy.deepcopy(d)
        del sin_media["capas"]["G"]["media"]
        sin_uniformidad = copy.deepcopy(d)
        del sin_uniformidad["uniformidad"]
        media_de_texto = copy.deepcopy(d)
        media_de_texto["capas"]["B"]["media"] = "88"
        tabla_nula = copy.deepcopy(d)
        tabla_nula["uniformidad"] = None                                  # una «ok» con la tabla en null: la clave esta, el contenido no
        for malo in (sin_media, sin_uniformidad, media_de_texto, tabla_nula):
            with pytest.raises(ValueError):
                pel.referencia_virgen_desde_dict(malo)

    def test_una_referencia_sin_la_media_esta_danada_aunque_no_sea_valida_y_con_la_media_en_null_se_lee(self, escaneo_virgen):
        """La clave `media` se exige SIEMPRE (una no valida la trae en null); lo que una «ok» ademas exige es que no sea null. Dos capas de defensa, cada una con su caso."""
        pel = _pel()
        d = json_ida_y_vuelta(escaneo_virgen.referencia.como_dict())
        d["estado"] = "no válida: fuera del rango esperado de una película sin irradiar"
        con_null = copy.deepcopy(d)
        for c in con_null["capas"].values():
            c["media"] = None
        assert pel.referencia_virgen_desde_dict(con_null).valor("G") is None
        sin_clave = copy.deepcopy(d)
        del sin_clave["capas"]["G"]["media"]
        with pytest.raises(ValueError):
            pel.referencia_virgen_desde_dict(sin_clave)

    def test_guardar_y_leer_la_referencia_conserva_la_media_y_la_uniformidad_y_la_pv_1_se_rechaza(self, escaneo_virgen, tmp_path):
        pel = _pel()
        pel.guardar_referencia_virgen(escaneo_virgen.referencia, str(tmp_path), escaneo_virgen.datos, "fisico")
        leida = pel.leer_referencia_virgen(str(tmp_path))
        assert leida.valor("G") == escaneo_virgen.referencia.valor("G") and leida.uniformidad == escaneo_virgen.referencia.uniformidad
        ruta = tmp_path / pel.ARCHIVO_REFERENCIA_VIRGEN
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        contenido["version"] = "PV-1"
        ruta.write_text(json.dumps(contenido), encoding="utf-8")
        with pytest.raises(ValueError) as e:
            pel.leer_referencia_virgen(str(tmp_path))
        assert "PV-1" in str(e.value) and "PV-2" in str(e.value)

    def test_la_virgen_sintetica_tiene_su_tabla_completa(self, escaneo_virgen):
        u = escaneo_virgen.referencia.uniformidad
        assert u["cabe"] is True and set(u["capas"]) == set(TODAS)
        for c in TODAS:
            fila = u["capas"][c]
            assert set(fila["regiones"]) == {"centro", "arriba", "abajo", "izquierda", "derecha"} and fila["centro"] == fila["regiones"]["centro"]
            assert fila["ruido"] > 0 and fila["uniformidad_pct"] >= 0
        assert escaneo_virgen.referencia.region["pelicula_mm"]["ancho"] == pytest.approx(115.0, abs=0.5), "la sintetica mide 115 x 116 mm"


def json_ida_y_vuelta(d):
    """El diccionario tal como lo devuelve json.loads(json.dumps(d)): listas, no tuplas."""
    return json.loads(json.dumps(d))


class TestUniformidadYRuidoPorSi:
    """La funcion pura, con una zona y unos planos de verdad conocida."""

    def _planos(self, alto=1500, ancho=1700, base=150.0, ruido=0.0, semilla=0):
        rng = np.random.default_rng(semilla)
        return {c: (base + 10 * i + (rng.normal(0, ruido, (alto, ancho)) if ruido else np.zeros((alto, ancho)))).astype(np.float32) for i, c in enumerate(TODAS)}

    def test_una_zona_uniforme_da_uniformidad_cero_y_el_ruido_que_se_puso(self):
        pel = _pel()
        zona = np.ones((1500, 1700), bool)
        u = pel.uniformidad_y_ruido(self._planos(ruido=2.0, semilla=3), zona, TAM)
        assert u["cabe"] is True
        for c in TODAS:
            assert u["capas"][c]["ruido"] == pytest.approx(2.0, abs=0.1) and u["capas"][c]["uniformidad_pct"] < 0.15

    def test_el_ruido_es_el_del_centro_y_no_el_de_toda_la_zona(self):
        """Ruido de 2 niveles SOLO en el centro: el ruido que se informa es el de la region central (2.0), no la desviacion de toda la zona (0.37)."""
        pel = _pel()
        planos = self._planos()
        rng = np.random.default_rng(5)
        for capa in TODAS:
            planos[capa][600:900, 700:1000] += rng.normal(0, 2.0, (300, 300)).astype(np.float32)
        u = pel.uniformidad_y_ruido(planos, np.ones((1500, 1700), bool), TAM)
        for capa in TODAS:
            assert u["capas"][capa]["ruido"] == pytest.approx(2.0, abs=0.15), (capa, u["capas"][capa]["ruido"])
            assert float(np.std(planos[capa])) < 0.5, "premisa: la desviacion de toda la zona es mucho menor"

    def test_un_escalon_en_una_region_es_la_uniformidad_que_se_midio(self):
        """Una region (izquierda) 3 niveles mas clara que el centro de 150: uniformidad = 3 / 150 = 2 %."""
        pel = _pel()
        planos = self._planos()
        zona = np.ones((1500, 1700), bool)
        ys, xs = np.nonzero(zona)
        mx = (xs.max() - xs.min()) / 4.0
        cx, lado = (xs.min() + xs.max()) / 2.0, int(round(10.0 / TAM))
        x1 = int(round(cx - mx - lado / 2.0))
        planos["R"][:, x1:x1 + lado] += 3.0
        u = pel.uniformidad_y_ruido(planos, zona, TAM)
        assert u["capas"]["R"]["uniformidad_pct"] == pytest.approx(2.0, abs=1e-4) and u["capas"]["G"]["uniformidad_pct"] == pytest.approx(0.0, abs=1e-6)
        assert u["capas"]["R"]["regiones"]["izquierda"] == pytest.approx(153.0, abs=1e-4)

    def test_las_regiones_miden_diez_por_diez_milimetros_y_estan_a_medio_camino_del_borde(self):
        pel = _pel()
        zona = np.ones((1500, 1700), bool)
        u = pel.uniformidad_y_ruido(self._planos(), zona, TAM)
        lado = int(round(10.0 / TAM))
        for nombre, caja in ((n, r["caja"]) for n, r in u["regiones"].items()):
            x0, y0, x1, y1 = caja
            assert (x1 - x0, y1 - y0) == (lado, lado), nombre
        cx = (u["regiones"]["centro"]["caja"][0] + u["regiones"]["centro"]["caja"][2]) / 2.0
        ix = (u["regiones"]["izquierda"]["caja"][0] + u["regiones"]["izquierda"]["caja"][2]) / 2.0
        assert cx - ix == pytest.approx(1699 / 4.0, abs=1.0), "a un cuarto del ancho util: a medio camino entre el centro y el borde"

    def test_un_nivel_en_cero_no_lanza_y_su_uniformidad_queda_sin_medir(self):
        """OD1-REV-PROD-02: la uniformidad es la mayor diferencia con el centro EN % del centro; con el centro en 0 no hay respecto de que medirla (antes: ZeroDivisionError con floats de Python). Las demas
        capas se miden como siempre y el ruido de la capa en cero es 0."""
        pel = _pel()
        planos = self._planos()
        planos["R"][:] = 0.0
        u = pel.uniformidad_y_ruido(planos, np.ones((1500, 1700), bool), TAM)
        assert u["cabe"] is True
        assert u["capas"]["R"]["centro"] == 0.0 and u["capas"]["R"]["uniformidad_pct"] is None and u["capas"]["R"]["ruido"] == 0.0
        for c in ("G", "B", "gris"):
            assert u["capas"][c]["uniformidad_pct"] == pytest.approx(0.0, abs=1e-9) and u["capas"][c]["centro"] > 0

    def test_si_una_region_no_cabe_se_dice_y_no_se_inventa_ningun_numero(self):
        pel = _pel()
        zona = np.zeros((1500, 1700), bool)
        zona[600:900, 600:1100] = True                                         # 300 x 500 px = 12.7 x 21 mm: el centro cabe, las de los lados no
        u = pel.uniformidad_y_ruido(self._planos(), zona, TAM)
        assert u["cabe"] is False
        for c in TODAS:
            assert u["capas"][c]["uniformidad_pct"] is None
        assert any(r["caja"] is None for r in u["regiones"].values())


# ===================================================================================================== (e) peliculas reales

CLICS = {
    "ML0": ((196, 143), (2542, 147), (2526, 2501), (171, 2480), (1371, 1330)),
    "EPSON007": ((207, 173), (2516, 153), (2553, 2507), (232, 2525), (1376, 1345)),
    "EPSON008_TIF": ((206, 189), (2517, 169), (2553, 2525), (230, 2542), (1376, 1362)),
    "EPSON030": ((166, 174), (2475, 158), (2507, 2512), (187, 2526), (1333, 1348)),
    "EPSON001_JPG": ((178, 255), (2541, 252), (2553, 2593), (203, 2608), (1368, 1435)),
    "EPSON001_TIF": ((178, 255), (2541, 252), (2553, 2593), (203, 2608), (1368, 1435)),
    "EPSON028": ((111, 200), (2452, 175), (2496, 2520), (124, 2525), (1287, 1362)),
    "EPSON029": ((215, 151), (2526, 195), (2494, 2542), (183, 2498), (1361, 1350)),
}
# El oraculo de la tarea (logs/OD/od_prevuelo.log, columna «OD-esq», y od_virgen_179.log, columna «OD-virg»): el FWHM [crossplane, inplane] de G, B y gris en mm, con el piso de las esquinas y con
# el piso FIJADO en la media de EPSON179 a 4 mm del borde (R 152.06, G 194.05, B 86.70, gris 169.24). El rojo de las ocho es «no medible» (meseta recortada).
# DECISION OD1-REV-D1 (22-10, opcion B): los CUATRO valores del azul inplane de EPSON007 y EPSON008.TIF (antes 95.85, 96.11, 96.04 y 96.19: el pre-vuelo promediaba la banda en lineal) son los de la IMAGEN
# CONVERTIDA PIXEL A PIXEL medida por una ruta independiente (scripts/od1_B_oraculo_imagen_convertida.py: 98.7792, 99.0848, 99.0296 y 99.1802 mm; con el piso FIJADO para los de «virgen»; log en
# logs/OD1/correccion_B/). Y el gris crossplane de EPSON029 con el piso de las esquinas (antes 97.62: con B el motor da 97.60899, 0.01101 mm del pre-vuelo, apenas fuera de los 0.011) toma el de la imagen
# convertida, 97.613 -> 97.61. Los otros 43 no cambian: el motor con B se mueve de -0.009 a +0.004 mm y la tolerancia sigue siendo 0.011.
PISO_FIJADO = {"R": 152.06, "G": 194.05, "B": 86.70, "gris": 169.24}
ORACULO = {
    "ML0": {"esquinas": {"G": (99.90, 99.62), "B": (99.26, 99.11), "gris": (100.15, 99.91)}, "virgen": {"G": (100.09, 99.84), "B": (99.54, 99.39), "gris": (100.44, 100.26)}},
    "EPSON007": {"esquinas": {"G": (98.62, 99.39), "B": (98.04, 98.78), "gris": (98.81, 99.63)}, "virgen": {"G": (98.79, 99.58), "B": (98.31, 99.08), "gris": (99.09, 99.95)}},
    "EPSON008_TIF": {"esquinas": {"G": (98.58, 99.35), "B": (97.95, 99.03), "gris": (98.77, 99.59)}, "virgen": {"G": (98.76, 99.54), "B": (98.14, 99.18), "gris": (99.06, 99.94)}},
    "EPSON030": {"esquinas": {"G": (98.57, 99.42), "B": (97.86, 98.93), "gris": (98.71, 99.66)}, "virgen": {"G": (98.74, 99.61), "B": (98.14, 99.44), "gris": (99.00, 99.98)}},
    "EPSON001_JPG": {"esquinas": {"G": (100.63, 98.61), "B": (99.67, 97.68), "gris": (100.85, 98.90)}, "virgen": {"G": (100.72, 98.74), "B": (100.09, 98.21), "gris": (101.02, 99.16)}},
    "EPSON001_TIF": {"virgen": {"G": (100.74, 98.75), "B": (100.04, 98.16), "gris": (101.03, 99.16)}},
    "EPSON028": {"esquinas": {"G": (100.68, 98.95), "B": (100.74, 98.75), "gris": (100.77, 99.38)}, "virgen": {"G": (100.79, 99.43), "B": (100.77, 98.89), "gris": (101.01, 99.93)}},
    "EPSON029": {"esquinas": {"G": (97.24, 99.76), "B": (96.41, 98.99), "gris": (97.61, 100.07)}, "virgen": {"G": (97.49, 99.97), "B": (96.71, 99.25), "gris": (97.96, 100.35)}},
}


def _referencia_con_el_piso_fijado():
    """Una `ReferenciaVirgen` valida cuyo valor por capa es EXACTAMENTE el del pre-vuelo (las medias a 4 mm de EPSON179): el piso «fijado» del oraculo."""
    pel = _pel()
    capas = {c: pel.CapaDelPiso(c, "ok", PISO_FIJADO[c], 1000, 1.0, None, None, PISO_FIJADO[c]) for c in TODAS}
    procedencia = {"archivo": "EPSON179.TIF", "sha256": "ab" * 32, "bytes": 1, "formato": "TIFF", "bits": 8, "dpi_declarado": 600.0, "clase_resolucion": "coincide", "forma": [6600, 5100],
                   "fecha_escaneo": None, "equipo": None, "calidad_jpeg": None, "submuestreo": None, "orientacion_declarada": None, "fecha_calculo": "2026-10-21", "version": pel.VERSION_PISO_VIRGEN}
    return pel.ReferenciaVirgen("ok", capas, (), (), {"caja": [0, 0, 1, 1], "n": 1000, "area_mm2": 1.0}, procedencia, {})


def _fwhm(res, capa):
    return tuple(getattr(res.capas[capa], eje).fwhm_mm for eje in EJES)


class TestPeliculasRealesContraElOraculoDelPreVuelo:
    @pytest.mark.parametrize("clave", sorted(ORACULO))
    def test_el_fwhm_del_verde_el_azul_y_el_gris_es_el_del_pre_vuelo_a_0_01_mm_y_el_rojo_no_es_medible(self, clave):
        pm = _pm()
        ruta = _corpus.pelicula(clave)
        if ruta is None:
            pytest.skip(f"HI-0: la pelicula real {clave} no esta")
        pelicula = _pel().leer_pelicula(Path(ruta).read_bytes())
        esperado = ORACULO[clave]
        corridas = []
        if "esquinas" in esperado:
            corridas.append(("esquinas", pm.analizar(pelicula, CLICS[clave], _P(BASE_OD), modo_piso="automatico")))
        corridas.append(("virgen", pm.analizar(pelicula, CLICS[clave], _P(BASE_OD), modo_piso="virgen", referencia_virgen=_referencia_con_el_piso_fijado())))
        for nombre, r in corridas:
            assert r.base == BASE_OD and r.estado == "ok", (clave, nombre, r.estado)
            assert r.piso.modo == ("virgen" if nombre == "virgen" else "automatico")
            for capa, (cruz, plano) in esperado[nombre].items():
                assert _fwhm(r, capa) == pytest.approx((cruz, plano), abs=0.011), (clave, nombre, capa, _fwhm(r, capa))
            rojo = r.capas["R"]
            assert not rojo.ok and rojo.estado.startswith("no medible") and pm.MOTIVO_MESETA_RECORTADA in rojo.estado, (clave, nombre, rojo.estado)
            assert pm.valores_medidos(r, "R")["estado"].startswith("no medible") and pm.valores_medidos(r, "R")["fwhm_crossplane_mm"] is None
            del r
        del corridas, pelicula
        gc.collect()

    def test_el_verde_en_netod_queda_a_un_milimetro_del_campo_luminoso_y_en_valor_de_pixel_no(self):
        """La causa de OD.1, medida con el motor de hoy: el verde en valor de pixel sale +1.0 a +2.4 mm del campo luminoso y en netOD a +-1 mm (EPSON008.TIF: luz 98.09 / 99.68 mm)."""
        pm = _pm()
        ruta = _corpus.pelicula("EPSON008_TIF")
        if ruta is None:
            pytest.skip("HI-0: EPSON008.TIF no esta")
        pelicula = _pel().leer_pelicula(Path(ruta).read_bytes())
        vp = pm.analizar(pelicula, CLICS["EPSON008_TIF"], _P(BASE_VP), modo_piso="automatico")
        od_ = pm.analizar(pelicula, CLICS["EPSON008_TIF"], _P(BASE_OD), modo_piso="automatico")
        luz = [(vp.bordes_luz_px[e][1] - vp.bordes_luz_px[e][0]) * vp.tam_mm for e in EJES]
        assert luz == pytest.approx([98.09, 99.68], abs=0.01)
        for eje, ancho_luz in zip(EJES, luz):
            en_vp = getattr(vp.capas["G"], eje).fwhm_mm - ancho_luz
            en_od = getattr(od_.capas["G"], eje).fwhm_mm - ancho_luz
            assert 0.9 < en_vp < 2.6, (eje, en_vp)
            assert abs(en_od) < 1.0, (eje, en_od)
        del vp, od_, pelicula
        gc.collect()


# ===================================================================================================== (h) la base de ida y vuelta por D.1

class TestLaBaseViajaEnLosParametrosGuardados:
    def _registro(self, sintetica, resultado, capa="G"):
        """Un registro como el que devuelve `leer` (sin pasar por la BD): lo que D.1 guarda de un analisis."""
        pm = _pm()
        valores = pm.valores_medidos(resultado, capa)
        return {"imagen": sintetica.datos, "puntos": list(resultado.marcas), "parametros": copy.deepcopy(resultado.parametros), "piso": resultado.piso.como_dict(), "capa": capa,
                "version": resultado.version, **valores}

    def test_un_registro_netod_se_recalcula_en_netod_aunque_la_constante_cambie(self, sintetica, analisis_od, monkeypatch):
        pm, svc = _pm(), _svc()
        registro = self._registro(sintetica, analisis_od)
        assert registro["parametros"]["base_de_la_medida"] == BASE_OD
        monkeypatch.setitem(pm.VALORES_DE_LA_GEOMETRIA, "base_de_la_medida", BASE_VP)           # «el fisico cambio BASE_POR_OMISION despues de guardar»
        recalculado = svc.recalcular(registro)
        assert recalculado.base == BASE_OD, "la copia guardada manda (DA-81): se mide con la base del registro, no con la de hoy"
        assert svc.diferencias(registro, recalculado) == []

    def test_un_registro_sin_el_parametro_se_recalcula_en_valor_de_pixel(self, sintetica):
        pm, svc = _pm(), _svc()
        vp = pm.analizar(sintetica.pelicula, sintetica.puntos, _P(BASE_VP), modo_piso="automatico")
        registro = self._registro(sintetica, vp)
        del registro["parametros"]["base_de_la_medida"]                                        # un registro de antes de OD.1: 40 parametros
        recalculado = svc.recalcular(registro)
        assert recalculado.base == BASE_VP and svc.diferencias(registro, recalculado) == []
        assert recalculado.parametros["base_de_la_medida"] == BASE_VP, "lo recalculado dice la base con que se midio"

    def test_si_la_base_del_registro_no_es_la_que_se_recalcula_la_diferencia_se_ve(self, sintetica, analisis_od):
        svc = _svc()
        registro = self._registro(sintetica, analisis_od)
        registro["parametros"]["base_de_la_medida"] = BASE_VP                                  # alguien edito el registro: lo guardado era netOD, los parametros dicen pixel
        recalculado = svc.recalcular(registro)
        assert recalculado.base == BASE_VP
        assert any("fwhm" in d for d in svc.diferencias(registro, recalculado)), "los FWHM guardados (netOD) ya no coinciden con lo recalculado (pixel)"

    def test_guardar_exige_todos_los_parametros_incluida_la_base(self, bd, placa, clics):
        svc = _svc()
        incompletos = {k: v for k, v in _pm().VALORES_DE_LA_GEOMETRIA.items() if k != "base_de_la_medida"}
        control = _un_control(bd)
        with pytest.raises(svc.PlacaMensualError) as e:
            svc.guardar(control, USUARIO, placa.datos, "p.png", clics, incompletos, "G", "automatico")
        assert "base_de_la_medida" in str(e.value)
        assert "los 40" not in (svc.guardar.__doc__ or ""), "la docstring dice «todos», no «los 40»"

    def test_guardar_y_leer_conserva_la_base_y_no_agrega_columnas(self, bd, placa, clics):
        pm, svc = _pm(), _svc()
        control = _un_control(bd)
        antes = _columnas(bd)
        nuevo = svc.guardar(control, USUARIO, placa.datos, "p.png", clics, _P(BASE_OD), "G", "automatico")
        registro = svc.leer(control)
        assert registro["id"] == nuevo and registro["parametros"]["base_de_la_medida"] == BASE_OD
        assert _columnas(bd) == antes and not [c for c in antes if "base" in c or "densidad" in c], "la base viaja en los parametros: ni una columna nueva"
        assert registro["fwhm_crossplane_mm"] is not None and registro["version"] == pm.VERSION_ALGORITMO
        recalculado = svc.recalcular(registro)
        assert recalculado.base == BASE_OD and svc.diferencias(registro, recalculado) == []
        del recalculado
        gc.collect()

    def test_el_mismo_analisis_guardado_en_las_dos_bases_da_otro_fwhm_del_verde(self, bd, placa, clics):
        svc = _svc()
        a, b = _un_control(bd), _un_control(bd)
        svc.guardar(a, USUARIO, placa.datos, "p.png", clics, _P(BASE_OD), "G", "automatico")
        svc.guardar(b, USUARIO, placa.datos, "p.png", clics, _P(BASE_VP), "G", "automatico")
        ra, rb = svc.leer(a), svc.leer(b)
        assert rb["fwhm_crossplane_mm"] - ra["fwhm_crossplane_mm"] > 0.5 and ra["parametros"]["base_de_la_medida"] != rb["parametros"]["base_de_la_medida"]


def _un_control(ruta):
    from test_d1_guardado_placa_mensual import _control
    return _control(ruta)


def _columnas(ruta):
    from test_d1_guardado_placa_mensual import _consulta
    return [c[1] for c in _consulta(ruta, "PRAGMA table_info('analisis_placa_mensual')")]


# ===================================================================================================== (i) la ventana y el dibujo

def _referencia_guardada(bd, escaneo):
    """Deja la referencia virgen vigente junto a la BD temporal (donde la ventana la busca)."""
    _pel().guardar_referencia_virgen(escaneo.referencia, os.path.dirname(bd), escaneo.datos, USUARIO)


def _ejes_de_los_perfiles(v):
    ejes = list(v._fig_perfiles.axes)
    assert len(ejes) == 8
    return dict(zip([(c, e) for c in (*CAPAS, "gris") for e in EJES], ejes))


class TestElDibujoDelPerfilEnLaBase:
    """OD1-REV-PRU-01. `dibujar_perfil` convierte a la unidad de la base CADA nivel que dibuja: el crudo, el suavizado, el piso, la meseta, la altura media, los DOS niveles de la penumbra y los limites del eje y.
    La prueba de la ventana solo miraba cuatro trazos y la etiqueta, y tres mutaciones que dejaban el suavizado, las lineas de la penumbra o el eje y en niveles de 8 bits sobre un eje de netOD sobrevivian. La verdad
    es la formula cerrada (`od`) y las fracciones del plan (la penumbra alta a 0.8, la altura media a 0.5 y la baja a 0.2 de la netOD de la meseta), no el codigo bajo prueba. Sin la ventana: un perfil de verdad
    conocida (el de dosis de netOD de meseta 0.7), medido y dibujado en un eje suelto."""

    def _dibujo(self, base):
        perfil, centro = perfil_de_dosis(0.7)
        medida = medir(perfil, centro, base)
        assert medida.ok, medida.estado
        ax = Figure().subplots(1, 1)
        _dib().dibujar_perfil(ax, medida, "G", _P(base))
        return ax, medida

    @staticmethod
    def _todo_lo_dibujado(ax):
        """Los valores y de cada trazo y de cada linea horizontal del perfil, en el orden en que el dibujo los pone."""
        gids = ("perfil:crudo", "perfil:suavizado", "perfil:piso", "perfil:meseta", "perfil:altura_media", "perfil:penumbra_alta", "perfil:penumbra_baja")
        return np.concatenate([np.asarray(por_gid(ax, g)[0].get_ydata(), float) for g in gids])

    def test_en_densidad_optica_neta_cada_nivel_dibujado_esta_en_netod_y_el_eje_lo_contiene(self):
        ax, m = self._dibujo(BASE_OD)
        piso, meseta, P = m.piso, m.meseta, _P(BASE_OD)
        netod = od(piso, meseta)
        assert ax.get_ylabel() == "densidad óptica neta [1]"
        en_netod = lambda niveles: np.log10(piso / np.maximum(np.asarray(niveles, float), VP_MINIMO))
        assert np.allclose(por_gid(ax, "perfil:crudo")[0].get_ydata(), en_netod(m.perfil.valores), atol=1e-9, equal_nan=True)
        assert np.allclose(por_gid(ax, "perfil:suavizado")[0].get_ydata(), en_netod(m.suavizado), atol=1e-9, equal_nan=True)
        for gid, esperado in (("perfil:piso", 0.0), ("perfil:meseta", netod), ("perfil:altura_media", P["altura_media"] * netod),
                              ("perfil:penumbra_alta", P["penumbra_alta"] * netod), ("perfil:penumbra_baja", P["penumbra_baja"] * netod)):
            linea = por_gid(ax, gid)
            assert len(linea) == 1 and np.allclose(linea[0].get_ydata(), esperado, atol=1e-9), (gid, linea[0].get_ydata(), esperado)
        dibujado = self._todo_lo_dibujado(ax)
        bajo, alto = ax.get_ylim()
        assert bajo <= np.nanmin(dibujado) and alto >= np.nanmax(dibujado), "el eje contiene todo lo dibujado"
        assert (np.nanmax(dibujado) - np.nanmin(dibujado)) >= 0.5 * (alto - bajo), f"el perfil llena el eje (no queda aplastado por limites en niveles de 8 bits): y de {bajo:.3f} a {alto:.3f}"

    def test_en_valor_de_pixel_cada_nivel_dibujado_es_el_nivel_de_8_bits_y_el_eje_lo_contiene(self):
        ax, m = self._dibujo(BASE_VP)
        P = _P(BASE_VP)
        assert ax.get_ylabel() == "valor de píxel [nivel]"
        assert np.allclose(por_gid(ax, "perfil:crudo")[0].get_ydata(), m.perfil.valores, atol=1e-9, equal_nan=True)
        assert np.allclose(por_gid(ax, "perfil:suavizado")[0].get_ydata(), m.suavizado, atol=1e-9, equal_nan=True)
        for gid, esperado in (("perfil:piso", m.piso), ("perfil:meseta", m.meseta), ("perfil:altura_media", m.piso - P["altura_media"] * (m.piso - m.meseta)),
                              ("perfil:penumbra_alta", m.piso - P["penumbra_alta"] * (m.piso - m.meseta)), ("perfil:penumbra_baja", m.piso - P["penumbra_baja"] * (m.piso - m.meseta))):
            assert np.allclose(por_gid(ax, gid)[0].get_ydata(), esperado, atol=1e-9), gid
        dibujado = self._todo_lo_dibujado(ax)
        bajo, alto = ax.get_ylim()
        assert bajo <= np.nanmin(dibujado) and alto >= np.nanmax(dibujado) and (np.nanmax(dibujado) - np.nanmin(dibujado)) >= 0.5 * (alto - bajo)


class TestLaVentana:
    def test_el_menu_piso_arranca_en_el_modo_efectivo(self, fabrica, bd, escaneo_virgen):
        sin = fabrica()
        assert sin.modo_del_piso == "automatico", "sin referencia, las esquinas (lo dice el menu)"
        _referencia_guardada(bd, escaneo_virgen)
        con = fabrica()
        assert con.modo_del_piso == "virgen" and "Película virgen «virgen_lote.tif»" in con.selector_piso.itemText(2)

    def test_con_la_referencia_vigente_el_analisis_usa_la_virgen_sin_tocar_el_menu(self, fabrica, dialogos, bd, escaneo_virgen, archivo_placa, clics):
        _referencia_guardada(bd, escaneo_virgen)
        v = fabrica()
        analizada(v, dialogos, archivo_placa, clics)
        r = v._resultado
        assert r.piso.modo == "virgen" and r.piso.referencia is not None and r.base == BASE_OD
        assert "película virgen «virgen_lote.tif»" in v.etiqueta_piso.text()

    def test_el_panel_dice_la_base_y_el_pie_tambien(self, fabrica, dialogos, archivo_placa, clics):
        v = fabrica()
        analizada(v, dialogos, archivo_placa, clics)
        assert v.etiqueta_piso.text().startswith(f"Base de la medida: {BASE_OD}"), v.etiqueta_piso.text()
        assert f"base de la medida: {BASE_OD}" in v.pie_de_parametros.text()

    def test_la_referencia_que_aparece_se_usa_sola_pero_una_eleccion_del_fisico_se_respeta(self, fabrica, dialogos, bd, escaneo_virgen, archivo_placa, clics, tmp_path):
        ruta_virgen = tmp_path / "virgen_lote.tif"
        ruta_virgen.write_bytes(escaneo_virgen.datos)
        # 1. el fisico no ha elegido nada: al guardar una referencia el piso pasa solo a la virgen y el analisis se repite con ella
        v = fabrica()
        analizada(v, dialogos, archivo_placa, clics)
        assert v._resultado.piso.modo == "automatico"
        dialogos.ruta = str(ruta_virgen)
        v.boton_virgen.click()
        assert v.modo_del_piso == "virgen" and v.estado == "analizada" and v._resultado.piso.modo == "virgen"
        # 2. el fisico ELIGIO el automatico: una referencia nueva no se lo cambia
        w = fabrica()
        _referencia_guardada(bd, escaneo_virgen)
        w.refrescar()
        analizada(w, dialogos, archivo_placa, clics)
        w.selector_piso.setCurrentIndex(0)
        assert w.modo_del_piso == "automatico" and w._resultado.piso.modo == "automatico"
        w.refrescar()
        assert w.modo_del_piso == "automatico" and w._resultado.piso.modo == "automatico", "la eleccion del fisico se respeta"

    def test_limpiar_devuelve_el_menu_al_modo_efectivo(self, fabrica, dialogos, bd, escaneo_virgen):
        _referencia_guardada(bd, escaneo_virgen)
        v = fabrica()
        v.selector_piso.setCurrentIndex(0)
        assert v.modo_del_piso == "automatico"
        assert v._modo_elegido, "premisa: el fisico lo eligio"
        v.boton_limpiar.click()
        assert v.modo_del_piso == "virgen"
        assert not v._modo_elegido, "Limpiar suelta la eleccion del fisico: lo siguiente que cambie (una referencia nueva) el menu lo sigue solo"

    def test_el_cuadro_de_la_virgen_muestra_su_uniformidad_y_su_ruido_sin_simbolos(self, fabrica, dialogos, escaneo_virgen, tmp_path):
        v = fabrica()
        ruta = tmp_path / "virgen_lote.tif"
        ruta.write_bytes(escaneo_virgen.datos)
        dialogos.ruta = str(ruta)
        v.boton_virgen.click()
        cuadro = dialogos.cuadros_de_la_virgen[-1]
        tabla = cuadro.tabla_uniformidad
        encabezados = [tabla.horizontalHeaderItem(c).text() for c in range(tabla.columnCount())]
        assert "Uniformidad [%]" in encabezados and "Ruido, desviación del centro [nivel]" in encabezados and tabla.rowCount() == 4
        assert cuadro.caja_de_la_pelicula.text() == _dib().texto_de_la_caja_de_la_pelicula(escaneo_virgen.referencia) and "mm" in cuadro.caja_de_la_pelicula.text()
        u = escaneo_virgen.referencia.uniformidad["capas"]
        for fila, capa in enumerate(TODAS):
            assert tabla.item(fila, encabezados.index("Uniformidad [%]")).text() == f"{u[capa]['uniformidad_pct']:.2f}"
            assert tabla.item(fila, encabezados.index("Ruido, desviación del centro [nivel]")).text() == f"{u[capa]['ruido']:.2f}"
        textos = [tabla.item(f, c).text() for f in range(tabla.rowCount()) for c in range(tabla.columnCount())] + encabezados + [cuadro.resumen.text(), cuadro.avisos.text(), cuadro.procedencia.text()]
        assert all(sin_simbolos(t) for t in textos)
        filas = [[cuadro.tabla_valores.item(f, c).text() for c in range(cuadro.tabla_valores.columnCount())] for f in range(cuadro.tabla_valores.rowCount())]
        for fila, capa in zip(filas, TODAS):
            assert float(fila[1]) == pytest.approx(escaneo_virgen.referencia.valor(capa), abs=0.051), "la tabla de valores muestra el valor del piso (la media)"

    def test_la_ayuda_del_boton_pide_escanear_donde_van_las_placas_o_una_hoja_entera(self, fabrica):
        v = fabrica()
        ayuda = v.boton_virgen.toolTip()
        assert "mismo lugar" in ayuda and "hoja" in ayuda and "600" in ayuda and "TIFF" in ayuda and sin_simbolos(ayuda)

    def test_los_perfiles_se_dibujan_en_densidad_optica_neta(self, fabrica, dialogos, archivo_placa, clics):
        v = fabrica()
        analizada(v, dialogos, archivo_placa, clics)
        ejes = _ejes_de_los_perfiles(v)
        for (capa, eje), ax in ejes.items():
            medida = getattr(v._resultado.capas[capa], eje)
            assert ax.get_ylabel() == "densidad óptica neta [1]", (capa, eje)
            if not medida.ok:
                continue
            piso, meseta = medida.piso, medida.meseta
            assert np.allclose(por_gid(ax, "perfil:piso")[0].get_ydata(), 0.0)
            assert np.allclose(por_gid(ax, "perfil:meseta")[0].get_ydata(), od(piso, meseta), atol=1e-9)
            assert np.allclose(por_gid(ax, "perfil:altura_media")[0].get_ydata(), 0.5 * od(piso, meseta), atol=1e-9)
            dibujado = por_gid(ax, "perfil:crudo")[0].get_ydata()
            esperado = np.log10(piso / np.maximum(medida.perfil.valores, VP_MINIMO))
            finitos = np.isfinite(esperado)
            assert np.allclose(np.asarray(dibujado)[finitos], esperado[finitos], atol=1e-9), (capa, eje)
            suave = np.log10(piso / np.maximum(medida.suavizado, VP_MINIMO))             # OD1-REV-PRU-01: el suavizado, las dos lineas de la penumbra y los limites del eje y tambien van en netOD
            fin_suave = np.isfinite(suave)
            assert np.allclose(np.asarray(por_gid(ax, "perfil:suavizado")[0].get_ydata())[fin_suave], suave[fin_suave], atol=1e-9), (capa, eje)
            assert np.allclose(por_gid(ax, "perfil:penumbra_alta")[0].get_ydata(), 0.8 * od(piso, meseta), atol=1e-9), (capa, eje)
            assert np.allclose(por_gid(ax, "perfil:penumbra_baja")[0].get_ydata(), 0.2 * od(piso, meseta), atol=1e-9), (capa, eje)
            bajo, alto = ax.get_ylim()
            assert alto - bajo < 10.0 and bajo <= 0.0 <= alto, (capa, eje, "el eje y esta en densidad optica (decimas a un par de unidades), no en niveles de 8 bits (de 0 a 255)")

    def test_un_analisis_guardado_en_valor_de_pixel_se_dibuja_en_valor_de_pixel(self, fabrica, dialogos, bd, placa, clics):
        control = _un_control(bd)
        svc = _svc()
        svc.guardar(control, USUARIO, placa.datos, "p.png", clics, _P(BASE_VP), "G", "automatico")
        v = fabrica(control)
        assert v.estado == "registro" and v._resultado.base == BASE_VP
        ax = _ejes_de_los_perfiles(v)[("G", "crossplane")]
        medida = v._resultado.capas["G"].crossplane
        assert ax.get_ylabel() == "valor de píxel [nivel]"
        assert np.allclose(por_gid(ax, "perfil:piso")[0].get_ydata(), medida.piso)
        assert f"base de la medida: {BASE_VP}" in v.pie_de_parametros.text()
        assert v.etiqueta_piso.text().startswith(f"Base de la medida: {BASE_VP}")

    def test_la_pestana_de_las_capas_se_acondiciona_en_la_base_del_analisis(self, analisis_od):
        dib = _dib()
        for capa in ("G", "B"):
            matriz, texto, meseta = dib.capa_acondicionada(analisis_od, capa)
            piso = analisis_od.capas[capa].piso
            girada = analisis_od.girada
            esperado = np.log10(piso / np.maximum(girada.capas[capa].astype(np.float64), VP_MINIMO)) / od(piso, meseta)
            esperado[~girada.validos] = np.nan
            visibles = np.isfinite(esperado)
            assert np.allclose(matriz[visibles], esperado[visibles], atol=2e-5), capa
            assert "0 es el piso" in texto and BASE_OD in texto

    def test_el_pie_de_parametros_no_falla_con_parametros_de_antes_de_od1(self):
        dib, pm = _dib(), _pm()
        sin = {k: v for k, v in pm.VALORES_DE_LA_GEOMETRIA.items() if k != "base_de_la_medida"}
        assert f"base de la medida: {BASE_VP}" in dib.texto_de_parametros(sin)
        assert dib.TRAZO_DE_PARAMETRO["base_de_la_medida"][0] == "pie" and len(dib.TRAZO_DE_PARAMETRO) == 41

    def test_el_texto_de_la_base_dice_la_formula_de_su_base(self):
        dib = _dib()
        netod, pixel = dib.texto_de_la_base(BASE_OD), dib.texto_de_la_base(BASE_VP)
        assert netod.startswith(f"Base de la medida: {BASE_OD};") and "log10(piso / valor) / log10(piso / meseta)" in netod and "media geométrica" in netod and "aritmética" not in netod
        assert pixel.startswith(f"Base de la medida: {BASE_VP};") and "(piso − valor) / (piso − meseta)" in pixel and "media aritmética" in pixel and "log10" not in pixel and "geométrica" not in pixel
        assert dib.texto_de_la_base("otra") == "Base de la medida: otra."

    def test_marcar_el_sexto_clic_es_elegir_el_piso_y_una_referencia_que_se_relee_despues_no_lo_cambia(self, fabrica, dialogos, bd, escaneo_virgen, archivo_placa, clics, placa):
        """Con una referencia vigente el menu arranca en la virgen; el sexto clic ES una eleccion del fisico (punto marcado) y releer la referencia (`refrescar`, que tambien corre al mostrar la ventana)
        no se lo quita."""
        _referencia_guardada(bd, escaneo_virgen)
        v = fabrica()
        assert v.modo_del_piso == "virgen" and not v._modo_elegido
        cargar(v, dialogos, archivo_placa)
        ul = placa.verdad.esquinas_pelicula_px["UL"]
        v.boton_sexto.click()
        clic(v, float(round(ul[0] + 90)), float(round(ul[1] + 90)))
        marcar(v, clics)
        assert v.modo_del_piso == "punto_manual" and v._resultado.piso.modo == "punto_manual" and v._modo_elegido
        v.refrescar()
        assert v.modo_del_piso == "punto_manual" and v._resultado.piso.modo == "punto_manual", "la eleccion del fisico se respeta"

    def test_los_textos_nuevos_no_llevan_simbolos(self, virgen_para_textos):
        dib = _dib()
        ref = virgen_para_textos
        textos = [t for fila in dib.filas_de_la_uniformidad(ref) for t in fila] + list(dib.COLUMNAS_DE_LA_UNIFORMIDAD) + [dib.texto_de_la_caja_de_la_pelicula(ref), dib.texto_de_la_base(BASE_OD),
                                                                                                                             dib.texto_de_la_base(BASE_VP)]
        assert all(isinstance(t, str) and t and sin_simbolos(t) for t in textos)


@pytest.fixture(scope="module")
def virgen_para_textos(escaneo_virgen):
    return escaneo_virgen.referencia


def test_el_documento_de_la_tarea_no_deja_la_base_escrita_dos_veces_en_la_ventana():
    """La ventana no escribe el nombre de ninguna base: lo dicen el motor y el dibujo (una operacion, una definicion)."""
    texto = (RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "placa_mensual.py").read_text(encoding="utf-8")
    assert BASE_OD not in texto and BASE_VP not in texto

