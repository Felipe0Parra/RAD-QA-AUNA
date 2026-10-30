"""CD.3 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, bloque CD.3): el MOTOR DE LA CURVA DE DOSIS, `analisisImagenes/curva_dosis.py` (sin Qt y sin base de datos).

CAUSA: la app no tenia como pasar de densidad optica a dosis, y H4 muestra que sin curva el 50 % del borde no es el de la dosis.

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale del motor: el generador `_piezas_de_calibracion_sinteticas.py` (la respuesta en dosis de cada capa, definida alli con su propia inversa;
una prueba por AST de CD.2 vigila que no importa nada del motor), las cuentas hechas aqui (los parametros de Devic, el optimo de los residuos relativos con una rejilla propia, la U) y los TIFF reales de
H9 contra la medida independiente del 22-10:
  (1) El modelo: D(x) = a·x + b·x^n, pasa por el origen, es impar para x < 0 (sin cambiar nada para x >= 0) y `netod` es su inversa (netod(dosis(x)) = x); la U (k = 2) de DC10.
  (2) Verdad conocida: con la respuesta de Devic exacta y sin ruido (16 bits) la dosis se recupera a ±0.5 % en todo el rango; con el ruido de EPSON179 (H2, 8 bits) a ±2 % por encima de 100 cGy.
  (3) El ajuste: los residuos RELATIVOS se minimizan de verdad (contra un optimo calculado aqui), n queda entre 1 y 4 aunque los datos pidan mas, y es determinista.
  (4) La honestidad del estado con una respuesta saturante que Devic no representa: «valida» si y solo si cada residuo del rango util esta en su tolerancia.
  (5) Los estados y el rango util (DC5): sin pieza de 0 cGy (guia), ninguna pieza medible, 5 dosis, datos no monotonos, el rojo recortado desde 400 cGy (el rango termina antes), la resolucion en
      dosis que se satura, una dosis medida que falta o no es positiva, piezas de otra cadena de captura y una pieza no medible que no entra.
  (6) El cero (DC3, CD-Z1): la media de las piezas de 0 cGy de LA MISMA calibracion; sin ellas la pelicula virgen montada de la misma cadena; sin ella la pieza de menor dosis (guia).
  (7) Los dos avisos (el fondo del escaner y otro lugar del vidrio) nombran su pieza y no cambian el estado.
  (8) La pieza de calibracion desde la `MedidaDePieza` de CD.2 (DC2: el valor y su u) y la lectura del fondo de la prueba C3.
  (9) Las 21 piezas reales de H9 (regla de PR.0): sus valores y su netOD son los de la medida independiente del 22-10; cada capa se ajusta y su estado y su rango se informan tal cual salen.
  (10) La copia guardada: `curva_desde_dict(como_dict())` da lo mismo y 30 formas danadas se rechazan con su motivo.
  (11) `PARAMETROS_DE_LA_CURVA` (PD1) y la estructura del modulo (sin Qt ni base, scipy arriba).
  (12) Ampliacion del implementador (29-10): las reglas que la bateria de mutaciones mostro sin guardia (la separacion, las replicas, los estados en los bordes, el cero de menor dosis, la cadena de captura de
       una pieza, los avisos en su frontera).
  (13) Correccion de la ronda 1 de la revision (30-10): una virgen angosta (sin su region central) no hace lanzar a `ajustar`, los avisos con cada fuente del cero, la cadena de captura y la pieza «ok» de una
       copia guardada, y el nombre de la pieza del cero.
  (14) La decision de Opus sobre CD3-PROD-01 y CD3-PROD-02 (30-10): `ajustar` nunca lanza por el contenido (una medida sin valor positivo no sirve de cero; en el modo guia las replicas del cero y lo que no
       supera su dosis no entran y se avisan; una pieza fuera del ajuste no trae residuo).
  (15) Ampliacion del corrector sobre esa decision (30-10): las guardas que los mutantes extra mostraron sin prueba (el modo guia con una dosis medida que falta, una pieza «no medible» o de 0 cGy, y las
       piezas con valor 0 solo en algunas capas).

Rojo contra HEAD (8bc91cc): el modulo no existe; caen todas las que lo usan (contadas aparte de las que caen por una asercion) y pasan las del generador, del corpus y de la regla de PR.0, que no lo
necesitan. El conteo va en `logs/CD3/rojo.log` del anexo.
"""
import ast
import copy
import dataclasses
import importlib
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import nnls

import _corpus
import _piezas_de_calibracion_sinteticas as gen

RAIZ = Path(__file__).resolve().parent.parent
FECHA = "2026-10-29"
CAPAS = ("R", "G", "B", "gris")
LAS_TRES = ("R", "G", "B")
DOSIS = (50, 100, 150, 200, 300, 400, 500, 600, 800, 1000)            # la plantilla del §7 del plan (sin la de 0 cGy)
DEVIC = (gen.RespuestaDevic(700.0, 3300.0, 2.06), gen.RespuestaDevic(1100.0, 4600.0, 2.19), gen.RespuestaDevic(1750.0, 8200.0, 1.58))      # una por capa (R, G, B), del orden de las de H9
SATURANTE = gen.RespuestaSaturante(0.45, 400.0)
SENSIBLE = gen.RespuestaDevic(600.0, 400.0, 2.0)                       # netOD 1.0 a 1000 cGy, como la reflexion de la WF-6590: la capa se oscurece hasta donde el ruido pesa
GRANDE = 50.0                                                          # piezas de 5 x 5 cm (§7): caben las cinco regiones de uniformidad y la u es la de sus medias (DC2)

# Los textos que fija el bloque y el pre-vuelo, ESCRITOS aqui (no importados del motor: CD2-M1).
VALIDA = "válida"
GUIA = "guía: el cero es la pieza de {dosis:g} cGy"
SIN_CERO = "incompleta: falta la película virgen (0 cGy)"
FALTA_DOSIS = "incompleta: falta la dosis medida de la pieza {orden} ({nominal:g} cGy)"
NO_POSITIVA = "incompleta: la dosis medida de la pieza {orden} ({nominal:g} cGy) no es positiva"
POCAS = "incompleta: quedan {n} dosis en el rango útil (hacen falta 6)"
NO_MONOTONOS = "no válida: datos no monótonos: la pieza de {nominal:g} cGy tiene menos densidad óptica que la de {anterior:g} cGy"
RESIDUO = "no válida: el residuo de la pieza de {nominal:g} cGy es {residuo:+.2f} % (la tolerancia es ±{tolerancia:g} %)"
OTRA_CADENA = "no válida: las piezas no se escanearon con la misma cadena de captura ("
RECORTE = "la capa está recortada por el escáner desde la pieza de {nominal:g} cGy"
RESOLUCION = "la resolución en dosis pasa de 3 % desde la pieza de {nominal:g} cGy (δD / D = "
SIN_RESOLUCION = "la resolución en dosis pasa de 3 % en todas las piezas"
FUERA = "la pieza {orden} ({nominal:g} cGy) no entra en la curva: {estado}"
EXPOSICION = "pieza {orden} ({nominal:g} cGy): el escáner pudo ajustar la exposición entre escaneos: el "
OTRO_LUGAR = "pieza {orden} ({nominal:g} cGy): la pieza se escaneó en otro lugar del vidrio: su centro está a "
VIRGEN_NO_SIRVE = "la película virgen montada no sirve de cero: se escaneó con otra cadena de captura ("
DANADA = "La curva de dosis está dañada: "
# (30-10, correccion de la ronda 1 de la revision, CD3-REV1-01 y CD3-REV1-03)
VIRGEN_SIN_CENTRO = "la película virgen montada no sirve de cero: no tiene la región central de la tabla de uniformidad y ruido, y sin ella no hay con qué medir su incertidumbre (DC2)"
CADENA_MAL_TIPADA = "no trae sus valores del tipo que se escribe"
OK_SIN_VALOR = "es «ok» y no trae su valor y su u como números de 0 o más"

# La netOD de cada pieza de H9 contra la de 5 cGy en la medida independiente del 22-10 (`logs/piezas_calibracion_22-10.log` del anexo, OpenCV, a 4 decimales): {dosis: (R, G, B)}.
NETOD_DE_H9_22_10 = {
    50: (0.0539, 0.0383, 0.0188), 100: (0.0971, 0.0686, 0.0304), 150: (0.1339, 0.0990, 0.0443), 200: (0.1653, 0.1275, 0.0576), 250: (0.1930, 0.1517, 0.0703),
    300: (0.2201, 0.1751, 0.0833), 350: (0.2461, 0.1976, 0.0959), 400: (0.2594, 0.2124, 0.1015), 450: (0.2838, 0.2333, 0.1126), 500: (0.2948, 0.2464, 0.1195),
    550: (0.3137, 0.2613, 0.1292), 600: (0.3307, 0.2772, 0.1382), 650: (0.3467, 0.2953, 0.1492), 700: (0.3553, 0.3045, 0.1509), 750: (0.3680, 0.3189, 0.1586),
    800: (0.3801, 0.3310, 0.1655), 850: (0.3942, 0.3458, 0.1769), 900: (0.4098, 0.3594, 0.1870), 950: (0.4216, 0.3720, 0.1932), 1000: (0.4273, 0.3801, 0.1964),
}
# Lo que dio el motor de referencia del pre-vuelo con las 21 piezas (29-10, `logs/CD3_prevuelo/h9_curva.log`): se informa tal cual sale (el bloque no espera «válida»; el cero es la pieza de 5 cGy).
H9_ESTADOS = {
    "R": "guía: el cero es la pieza de 5 cGy",
    "G": "no válida: el residuo de la pieza de 350 cGy es +3.19 % (la tolerancia es ±3 %)",
    "B": "incompleta: quedan 0 dosis en el rango útil (hacen falta 6)",
    "gris": "no válida: el residuo de la pieza de 350 cGy es +3.60 % (la tolerancia es ±3 %)",
}
H9_RANGOS = {"R": 445.0, "G": 645.0, "B": None, "gris": 645.0}


# ===================================================================================================== ayudas

def _cd():
    """El modulo, importado POR PRUEBA (en HEAD no existe y cada prueba que lo usa cae con su error)."""
    return importlib.import_module("analisisImagenes.curva_dosis")


def _pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _P():
    return copy.deepcopy(importlib.import_module("analisisImagenes.placa_mensual").VALORES_DE_LA_GEOMETRIA)


def medir(datos, nombre="pieza.tif", escala="declarada"):
    return _pel().medir_pieza_uniforme(datos, _P(), nombre, FECHA, escala=escala)


def pieza(orden, dosis, respuestas=DEVIC, medida="nominal", **opciones):
    """La `PiezaDeCalibracion` de una pieza sintetica irradiada a `dosis` (la de 0 cGy, sin irradiar): su dosis medida es la nominal salvo que se diga otra (None = falta)."""
    opciones.setdefault("semilla", orden)
    m = medir(gen.pieza_de_dosis(dosis, respuestas, **opciones).datos, f"{dosis}.tif")
    return _cd().pieza_de_calibracion(orden, float(dosis), float(dosis) if medida == "nominal" else medida, m)


def calibracion(dosis=DOSIS, respuestas=DEVIC, cero=True, **opciones):
    """Las piezas de una calibracion sintetica: la de 0 cGy (orden 1, si `cero`) y una por dosis."""
    piezas = [pieza(1, 0, respuestas, 0.0, **opciones)] if cero else []
    return piezas + [pieza(k + 2, d, respuestas, **opciones) for k, d in enumerate(dosis)]


def devic(x, a, b, n):
    return a * x + b * x ** n


def verdad(capa):
    return DEVIC[LAS_TRES.index(capa)]


@pytest.fixture(scope="module")
def grande():
    """La plantilla del §7 en piezas de 5 x 5 cm con el ruido de EPSON179 (8 bits): todas validas."""
    return _cd().ajustar(calibracion(lado_mm=GRANDE))


@pytest.fixture(scope="module")
def exacta():
    """La misma, sin ruido y en 16 bits (en 8 bits el redondeo a niveles enteros mueve la curva: logs/CD3_prevuelo/verdad_conocida.log)."""
    return _cd().ajustar(calibracion(lado_mm=GRANDE, sigma=0.0, bits=16))


# ===================================================================================================== (1) el modelo

class TestElModelo:
    def test_dosis_es_devic_y_pasa_por_el_origen(self, grande):
        for capa in CAPAS:
            p = grande.capas[capa]["parametros"]
            assert grande.dosis(capa, 0.0) == 0.0
            for x in (0.01, 0.1, 0.25, 0.4):
                assert grande.dosis(capa, x) == pytest.approx(devic(x, p["a"], p["b"], p["n"]), rel=1e-12)

    def test_la_extension_impar_no_cambia_nada_para_x_positivo(self, grande):
        x = np.linspace(-0.05, 0.4, 91)
        d = grande.dosis("G", x)
        assert isinstance(d, np.ndarray) and d.shape == x.shape
        assert np.allclose(d[x >= 0], [grande.dosis("G", float(v)) for v in x[x >= 0]], rtol=0, atol=0)
        assert np.allclose(grande.dosis("G", -x), -d, rtol=0, atol=1e-12)
        assert -5.0 < grande.dosis("G", -0.002) < 0.0, "el ruido bajo la virgen da una dosis negativa pequena (unos -2 cGy), sin romper"

    def test_netod_es_la_inversa_de_dosis(self, grande):
        for capa in CAPAS:
            for x in (-0.03, 0.0, 1e-4, 0.05, 0.2, 0.39, 0.8):
                assert abs(grande.netod(capa, grande.dosis(capa, x)) - x) <= 1e-9, (capa, x)
            d = np.array([0.0, 1.0, 50.0, 400.0, 999.0, -20.0])
            assert np.allclose(grande.dosis(capa, grande.netod(capa, d)), d, rtol=1e-9, atol=1e-7)

    def test_sin_parametros_no_hay_curva(self):
        c = _cd().ajustar([])
        for capa in CAPAS:
            assert c.estado(capa) == SIN_CERO and c.rango(capa) is None
            with pytest.raises(ValueError, match="no tiene curva"):
                c.dosis(capa, 0.1)
            with pytest.raises(ValueError, match="no tiene curva"):
                c.netod(capa, 100.0)

    def test_la_incertidumbre_es_la_de_dc10(self, grande):
        cd = _cd()
        capa, x, u_x = "G", 0.2, 0.004
        p, rms = grande.capas[capa]["parametros"], grande.capas[capa]["rms_pct"] / 100.0
        d, derivada = devic(x, p["a"], p["b"], p["n"]), p["a"] + p["n"] * p["b"] * x ** (p["n"] - 1)
        assert grande.incertidumbre(capa, x, u_x) == pytest.approx(2 * math.sqrt((d * rms) ** 2 + (u_x * derivada) ** 2), rel=1e-12)
        con_camara = cd.curva_desde_dict({**grande.como_dict(), "u_dosis_medida_pct": 2.0})
        assert con_camara.incertidumbre(capa, x, u_x) == pytest.approx(2 * math.sqrt((d * rms) ** 2 + (d * 0.02) ** 2 + (u_x * derivada) ** 2), rel=1e-12)
        assert grande.incertidumbre(capa, 0.0, u_x) == pytest.approx(2 * u_x * p["a"], rel=1e-12), "en x = 0 queda la de la pelicula sola"


# ===================================================================================================== (2) verdad conocida

class TestVerdadConocida:
    @pytest.mark.parametrize("capa", LAS_TRES)
    def test_sin_ruido_la_dosis_se_recupera_a_medio_por_ciento_en_todo_el_rango(self, exacta, capa):
        assert exacta.estado(capa) == VALIDA and exacta.rango(capa) == 1000.0
        r = verdad(capa)
        for x in np.linspace(0.002, exacta.capas[capa]["netod_maxima"], 60):
            assert abs(exacta.dosis(capa, x) - r.dosis(x)) <= 0.005 * r.dosis(x), (capa, x)

    @pytest.mark.parametrize("capa", LAS_TRES)
    def test_con_el_ruido_de_h2_la_dosis_se_recupera_a_dos_por_ciento_sobre_100_cgy(self, grande, capa):
        assert grande.estado(capa) == VALIDA
        r = verdad(capa)
        for x in np.linspace(r.netod(100.0), grande.capas[capa]["netod_maxima"], 40):
            assert abs(grande.dosis(capa, x) - r.dosis(x)) <= 0.02 * r.dosis(x), (capa, x)
        for p in grande.piezas:
            if p.dosis_nominal_cgy >= 100:
                assert abs(grande.dosis(capa, p.capas[capa]["netod"]) - p.dosis_nominal_cgy) <= 0.02 * p.dosis_nominal_cgy

    def test_con_piezas_chicas_y_el_ruido_de_h2_el_verde_tambien(self):
        c = _cd().ajustar(calibracion())
        r = verdad("G")
        assert c.estado("G") == VALIDA
        for x in np.linspace(r.netod(100.0), c.capas["G"]["netod_maxima"], 40):
            assert abs(c.dosis("G", x) - r.dosis(x)) <= 0.02 * r.dosis(x)


# ===================================================================================================== (3) el ajuste

def _optimo_relativo(x, d):
    """El minimo de Σ ((a·x + b·x^n − D) / D)² con a, b >= 0 y 1 <= n <= 4, calculado AQUI con una rejilla fina de n (cada 0.001) y a, b exactos: la verdad con que se juzga el ajuste."""
    return min(nnls(np.column_stack((x / d, x ** n / d)), np.ones_like(d))[1] ** 2 for n in np.linspace(1.0, 4.0, 3001))


def _del_rango(curva, capa):
    piezas = [p for p in curva.piezas if p.capas[capa]["en_el_rango"]]
    return np.array([p.capas[capa]["netod"] for p in piezas]), np.array([p.capas[capa]["dosis_cgy"] for p in piezas]), piezas


class TestElAjuste:
    @pytest.mark.parametrize("respuesta", ["devic", "saturante"])
    def test_minimiza_los_residuos_relativos(self, grande, respuesta):
        curva = grande if respuesta == "devic" else _cd().ajustar(calibracion(respuestas=SATURANTE, lado_mm=GRANDE))
        for capa in LAS_TRES:
            x, d, _ = _del_rango(curva, capa)
            p = curva.capas[capa]["parametros"]
            costo = float(np.sum(((devic(x, p["a"], p["b"], p["n"]) - d) / d) ** 2))
            assert costo == pytest.approx(curva.capas[capa]["costo"], rel=1e-9, abs=1e-15)
            assert costo <= _optimo_relativo(x, d) * (1 + 1e-6) + 1e-15, (capa, costo)

    def test_el_rms_y_los_residuos_son_los_de_sus_parametros(self, grande):
        for capa in CAPAS:
            x, d, piezas = _del_rango(grande, capa)
            p = grande.capas[capa]["parametros"]
            residuos = 100 * (devic(x, p["a"], p["b"], p["n"]) - d) / d
            assert [q.capas[capa]["residuo_pct"] for q in piezas] == pytest.approx(list(residuos), rel=1e-9, abs=1e-12)
            assert grande.capas[capa]["rms_pct"] == pytest.approx(float(np.sqrt(np.mean(residuos ** 2))), rel=1e-9)

    def test_n_queda_entre_1_y_4_aunque_los_datos_pidan_mas(self):
        c = _cd().ajustar(calibracion(respuestas=gen.RespuestaDevic(300.0, 30000.0, 5.5), lado_mm=GRANDE))
        assert all(c.capas[capa]["parametros"]["n"] == 4.0 for capa in LAS_TRES), {k: v["parametros"] for k, v in c.capas.items()}
        s = _cd().ajustar(calibracion(respuestas=SATURANTE, lado_mm=GRANDE))
        assert all(1.0 <= s.capas[capa]["parametros"]["n"] <= 4.0 for capa in CAPAS)

    def test_es_determinista(self):
        piezas = calibracion(lado_mm=GRANDE)
        assert json.dumps(_cd().ajustar(piezas).como_dict(), sort_keys=True) == json.dumps(_cd().ajustar(list(reversed(piezas))).como_dict(), sort_keys=True)

    def test_a_y_b_no_son_negativos(self, grande):
        assert all(grande.capas[c]["parametros"]["a"] >= 0 and grande.capas[c]["parametros"]["b"] >= 0 for c in CAPAS)


# ===================================================================================================== (4) la honestidad del estado

class TestLaHonestidadDelEstado:
    @pytest.mark.parametrize("lado", [GRANDE, 18.0])
    def test_con_una_respuesta_saturante_el_estado_sigue_la_tolerancia(self, lado):
        c = _cd().ajustar(calibracion(respuestas=SATURANTE, lado_mm=lado))
        for capa in CAPAS:
            if c.capas[capa]["parametros"] is None or c.rango(capa) is None or c.estado(capa).startswith("incompleta"):
                continue
            fuera = [q for q in c.piezas if q.capas[capa]["en_el_rango"]
                     and abs(q.capas[capa]["residuo_pct"]) > (5.0 if q.capas[capa]["dosis_cgy"] < 100 else 3.0)]
            assert (c.estado(capa) == VALIDA) == (not fuera), (capa, c.estado(capa), [(q.dosis_nominal_cgy, q.capas[capa]["residuo_pct"]) for q in fuera])
            if fuera:
                q = fuera[0]
                assert c.estado(capa) == RESIDUO.format(nominal=q.dosis_nominal_cgy, residuo=q.capas[capa]["residuo_pct"], tolerancia=5 if q.capas[capa]["dosis_cgy"] < 100 else 3)

    def test_la_saturante_no_es_valida_y_lo_dice_con_su_pieza(self):
        c = _cd().ajustar(calibracion(respuestas=SATURANTE, lado_mm=GRANDE))
        assert all(c.estado(capa).startswith("no válida: el residuo de la pieza de ") for capa in LAS_TRES), {k: c.estado(k) for k in CAPAS}


# ===================================================================================================== (5) los estados y el rango util

class TestLosEstados:
    def test_sin_pieza_de_0_cgy_el_cero_es_la_de_menor_dosis_y_es_una_guia(self):
        c = _cd().ajustar(calibracion(cero=False, lado_mm=GRANDE))
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and c.cero["dosis_cgy"] == 50.0
        for capa in CAPAS:
            assert c.estado(capa) == GUIA.format(dosis=50), (capa, c.estado(capa))
            assert c.rango(capa) == 950.0, "las dosis se cuentan desde el cero (1000 - 50)"

    def test_sin_ninguna_pieza_medible_falta_la_pelicula_virgen(self):
        piezas = [_cd().pieza_de_calibracion(k + 1, float(d), float(d), medir(b"no es una imagen", f"{d}.tif")) for k, d in enumerate((0, 100, 200))]
        c = _cd().ajustar(piezas)
        assert c.cero is None and all(c.estado(capa) == SIN_CERO for capa in CAPAS)
        assert c.avisos == tuple(FUERA.format(orden=q.orden, nominal=q.dosis_nominal_cgy, estado=q.estado) for q in piezas)

    def test_con_5_dosis_esta_incompleta_y_con_6_es_valida(self):
        cinco = _cd().ajustar(calibracion(dosis=(100, 200, 400, 600, 800), lado_mm=GRANDE))
        seis = _cd().ajustar(calibracion(dosis=(100, 200, 400, 600, 800, 1000), lado_mm=GRANDE))
        for capa in LAS_TRES:
            assert cinco.estado(capa) == POCAS.format(n=5) and cinco.capas[capa]["dosis_en_el_rango"] == 5
            assert seis.estado(capa) == VALIDA and seis.capas[capa]["dosis_en_el_rango"] == 6

    def test_las_replicas_cuentan_una_vez(self):
        piezas = calibracion(dosis=(100, 200, 400, 600, 800), lado_mm=GRANDE)
        replicas = piezas + [pieza(20 + k, d, lado_mm=GRANDE) for k, d in enumerate((100, 200, 400, 600, 800))]
        c = _cd().ajustar(replicas)
        assert all(c.estado(capa) == POCAS.format(n=5) for capa in LAS_TRES)
        assert sum(q.capas["G"]["en_el_rango"] for q in c.piezas) == 10

    def test_datos_no_monotonos(self):
        piezas = calibracion(lado_mm=GRANDE)
        cambiadas = [q if q.dosis_nominal_cgy not in (200.0, 400.0) else _cd().pieza_de_calibracion(q.orden, 600.0 - q.dosis_nominal_cgy, 600.0 - q.dosis_nominal_cgy, q.medida)
                     for q in piezas]                                            # las piezas de 200 y 400 cGy cambiadas de fila
        c = _cd().ajustar(cambiadas)
        for capa in LAS_TRES:
            assert c.estado(capa) == NO_MONOTONOS.format(nominal=300, anterior=200), (capa, c.estado(capa))

    def test_el_rojo_recortado_desde_400_cgy_termina_el_rango_antes(self):
        c = _cd().ajustar(calibracion(lado_mm=GRANDE, negro_desde_cgy={"R": 400}))
        assert c.rango("R") == 300.0 and c.capas["R"]["limite"] == RECORTE.format(nominal=400)
        assert c.estado("R") == POCAS.format(n=5)
        assert [q.capas["R"]["recortada"] is not None for q in c.piezas] == [q.dosis_nominal_cgy >= 400 for q in c.piezas]
        assert all(not q.capas["R"]["en_el_rango"] for q in c.piezas if q.dosis_nominal_cgy >= 400)
        assert c.estado("G") == VALIDA and c.rango("G") == 1000.0, "las otras capas no cambian: cada capa por separado (PD3)"

    def test_la_resolucion_en_dosis_que_se_satura_termina_el_rango(self):
        c = _cd().ajustar(calibracion(respuestas=SENSIBLE))
        assert c.rango("R") == 400.0 and c.capas["R"]["limite"].startswith(RESOLUCION.format(nominal=500)), c.capas["R"]["limite"]
        assert c.estado("R") == VALIDA and c.capas["R"]["dosis_en_el_rango"] == 6
        assert c.rango("G") == 1000.0 and c.capas["G"]["limite"] is None
        assert c.capas["B"]["limite"] == SIN_RESOLUCION and c.rango("B") is None and c.estado("B") == POCAS.format(n=0)

    def test_el_rango_y_el_ajuste_son_de_la_misma_vuelta(self, monkeypatch):
        """Si al rehacer el ajuste con las dosis del rango ninguna cumple la resolucion (c), la capa queda SIN rango: nunca el rango de una vuelta con el ajuste de otra. La segunda vuelta se fuerza con
        un ajuste que no resuelve ninguna dosis (a = 0 y n = 4: δD / D = 4 · u / x), porque con datos sinteticos el ajuste rehecho siempre resuelve alguna."""
        cd = _cd()
        real, vueltas = cd._ajustar_devic, []

        def ajuste(x, d):
            vueltas.append(len(x))
            a, b, n, costo = real(x, d)
            return (a, b, n, costo) if len(vueltas) == 1 else (0.0, b, 4.0, costo)

        piezas = calibracion(respuestas=SENSIBLE)
        monkeypatch.setattr(cd, "_ajustar_devic", ajuste)
        c = cd.ajustar(piezas)
        assert vueltas[:2] == [10, 6], "el rojo se ajusta con las 10 dosis, la resolucion lo corta en 6 y se rehace"
        assert c.rango("R") is None and c.capas["R"]["dosis_en_el_rango"] == 0 and c.capas["R"]["netod_maxima"] is None
        assert c.capas["R"]["limite"] == SIN_RESOLUCION and c.estado("R") == POCAS.format(n=0)

    def test_una_dosis_medida_que_falta_o_no_es_positiva(self):
        piezas = calibracion(lado_mm=GRANDE)
        sin = [q if q.orden != 3 else _cd().pieza_de_calibracion(3, 100.0, None, q.medida) for q in piezas]
        cero = [q if q.orden != 3 else _cd().pieza_de_calibracion(3, 100.0, 0.0, q.medida) for q in piezas]
        assert all(_cd().ajustar(sin).estado(capa) == FALTA_DOSIS.format(orden=3, nominal=100) for capa in CAPAS)
        assert all(_cd().ajustar(cero).estado(capa) == NO_POSITIVA.format(orden=3, nominal=100) for capa in CAPAS)

    def test_piezas_de_otra_cadena_de_captura(self):
        piezas = calibracion(lado_mm=GRANDE)
        piezas[4] = pieza(piezas[4].orden, piezas[4].dosis_nominal_cgy, lado_mm=GRANDE, bits=16)
        c = _cd().ajustar(piezas)
        assert c.cadena is None and all(c.estado(capa).startswith(OTRA_CADENA) for capa in CAPAS)
        assert "8 bits" in c.estado("G") and "16 bits" in c.estado("G")

    def test_una_pieza_no_medible_no_entra_y_se_avisa(self, grande):
        piezas = calibracion(lado_mm=GRANDE) + [_cd().pieza_de_calibracion(30, 700.0, 700.0, medir(b"basura", "700.tif"))]
        c = _cd().ajustar(piezas)
        assert c.avisos == (FUERA.format(orden=30, nominal=700, estado=piezas[-1].estado),)
        assert {k: c.estado(k) for k in CAPAS} == {k: grande.estado(k) for k in CAPAS}

    def test_los_parametros_se_pueden_cambiar_y_viajan_con_la_curva(self):
        piezas = calibracion(dosis=(100, 200, 400, 600, 800), lado_mm=GRANDE)
        c = _cd().ajustar(piezas, {"piezas_minimas": 5})
        assert c.estado("G") == VALIDA and c.parametros["piezas_minimas"] == 5 and c.parametros["residuo_maximo_pct"] == 3.0


# ===================================================================================================== (6) el cero

def _virgen(valores=(152.12, 194.11, 86.77), dpi=600.0):
    """Una pelicula virgen sintetica de 60 x 60 mm centrada en una pagina, medida como la de OD.1 (escala del procedimiento: 600 ppp)."""
    lienzo = gen.Lienzo(66.0, 66.0, dpi, semilla=9)
    lienzo.pegar_pelicula(3.0, 3.0, 60.0, 60.0, valores, gen.RUIDO_EPSON179)
    return _pel().piso_de_pelicula_virgen(lienzo.codificar(), _P(), "virgen.tif", FECHA)


class TestElCero:
    def test_i0_es_la_media_de_las_piezas_de_0_cgy_de_la_misma_calibracion(self):
        piezas = calibracion(lado_mm=GRANDE) + [pieza(40, 0, medida=0.0, lado_mm=GRANDE, i0=(150.0, 190.0, 85.0))]
        c = _cd().ajustar(piezas)
        ceros = [q for q in piezas if q.dosis_nominal_cgy == 0]
        assert len(ceros) == 2 and c.cero["fuente"] == "piezas_de_0_cgy" and c.cero["dosis_cgy"] == 0.0
        for capa in CAPAS:
            i0 = (ceros[0].capas[capa]["valor"] + ceros[1].capas[capa]["valor"]) / 2
            assert c.cero["capas"][capa]["i0"] == pytest.approx(i0, rel=1e-12)
            assert c.cero["capas"][capa]["u_i0"] == pytest.approx(math.sqrt((ceros[0].capas[capa]["u"] ** 2 + ceros[1].capas[capa]["u"] ** 2) / 2), rel=1e-12)
            for q in c.piezas:
                if q.dosis_nominal_cgy > 0:
                    assert q.capas[capa]["netod"] == pytest.approx(math.log10(i0 / q.capas[capa]["valor"]), rel=1e-12)
                    u = math.sqrt((c.cero["capas"][capa]["u_i0"] / i0) ** 2 + (q.capas[capa]["u"] / q.capas[capa]["valor"]) ** 2) / math.log(10)
                    assert q.capas[capa]["u_netod"] == pytest.approx(u, rel=1e-12)

    def test_sin_piezas_de_0_cgy_la_virgen_montada_de_la_misma_cadena(self):
        virgen = _virgen()
        assert virgen.estado == "ok", virgen.estado
        piezas = calibracion(cero=False, dpi=600.0, lado_mm=18.0)
        c = _cd().ajustar(piezas, virgen=virgen)
        assert c.cero["fuente"] == "pelicula_virgen" and c.cero["dosis_cgy"] == 0.0 and "virgen.tif" in c.cero["detalle"]
        for capa in CAPAS:
            assert c.cero["capas"][capa]["i0"] == virgen.valor(capa)
            assert virgen.uniformidad["cabe"] and c.cero["capas"][capa]["u_i0"] == pytest.approx(float(np.std(list(virgen.uniformidad["capas"][capa]["regiones"].values()), ddof=1)), rel=1e-12), \
                "la u de la virgen que hace de cero es la desviacion de las medias de sus cinco regiones (DC2, CD3-D7)"
            assert not c.estado(capa).startswith("guía")
        assert c.estado("G") == VALIDA

    def test_la_virgen_de_otra_cadena_no_hace_de_cero(self):
        c = _cd().ajustar(calibracion(cero=False, lado_mm=GRANDE), virgen=_virgen())
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and any(a.startswith(VIRGEN_NO_SIRVE) for a in c.avisos), c.avisos
        assert c.estado("G") == GUIA.format(dosis=50)

    def test_las_piezas_de_0_cgy_van_antes_que_la_virgen(self):
        c = _cd().ajustar(calibracion(dpi=600.0, lado_mm=18.0), virgen=_virgen())
        assert c.cero["fuente"] == "piezas_de_0_cgy"


# ===================================================================================================== (7) los avisos

class TestLosAvisos:
    def test_el_fondo_distinto_nombra_su_pieza_y_no_cambia_el_estado(self):
        normal = calibracion(lado_mm=18.0, margen_mm=10.0)
        otra = [q if q.orden != 5 else pieza(5, q.dosis_nominal_cgy, lado_mm=18.0, margen_mm=10.0, blanco=250.0) for q in normal]
        a, b = _cd().ajustar(normal), _cd().ajustar(otra)
        assert a.avisos == () and len(b.avisos) == 1 and b.avisos[0].startswith(EXPOSICION.format(orden=5, nominal=200)), b.avisos
        assert {k: b.estado(k) for k in CAPAS} == {k: a.estado(k) for k in CAPAS}
        assert normal[4].fondo_blanco == 1.0 and otra[4].fondo_blanco == 0.0

    def test_otro_lugar_del_vidrio_nombra_su_pieza_y_no_cambia_el_estado(self):
        aqui = dict(pagina_mm=(110.0, 40.0), posicion_mm=(10.0, 10.0))
        normal = calibracion(lado_mm=18.0, **aqui)
        lejos = [q if q.orden != 6 else pieza(6, q.dosis_nominal_cgy, lado_mm=18.0, pagina_mm=(110.0, 40.0), posicion_mm=(40.0, 10.0)) for q in normal]
        a, b = _cd().ajustar(normal), _cd().ajustar(lejos)
        assert a.avisos == () and len(b.avisos) == 1 and b.avisos[0].startswith(OTRO_LUGAR.format(orden=6, nominal=300)), b.avisos
        assert "a 30.0 mm del centro del cero (más de 20 mm)" in b.avisos[0]
        assert {k: b.estado(k) for k in CAPAS} == {k: a.estado(k) for k in CAPAS}


# ===================================================================================================== (8) la pieza de calibracion

class TestLaPiezaDeCalibracion:
    def test_el_valor_y_su_u_salen_de_la_medida_de_cd2(self):
        chica, grande_ = pieza(2, 200, lado_mm=18.0), pieza(3, 200, lado_mm=GRANDE)
        for q in (chica, grande_):
            for capa in CAPAS:
                assert q.capas[capa]["valor"] == q.medida.valor(capa) and q.capas[capa]["netod"] is None
        assert chica.medida.uniformidad["cabe"] is False and grande_.medida.uniformidad["cabe"] is True
        for capa in CAPAS:
            assert chica.capas[capa]["u"] == chica.medida.centro[capa]["desviacion"], "si no caben las cinco regiones, la de los pixeles del centro (DC2)"
            medias = list(grande_.medida.uniformidad["capas"][capa]["regiones"].values())
            assert grande_.capas[capa]["u"] == pytest.approx(float(np.std(medias, ddof=1)), rel=1e-12), "si caben, la desviacion de sus cinco medias (DC2)"

    def test_su_posicion_y_su_fondo(self):
        q = pieza(2, 200, lado_mm=18.0, pagina_mm=(110.0, 40.0), posicion_mm=(40.0, 10.0))
        assert q.posicion_mm == pytest.approx({"x": 49.0, "y": 19.0}, abs=0.2) and q.fondo_blanco == 1.0
        assert pieza(3, 200, lado_mm=18.0).fondo_blanco is None, "un recorte a ras no trae fondo: no se juzga"

    def test_una_medida_no_medible_no_trae_numeros(self):
        q = _cd().pieza_de_calibracion(1, 100.0, 100.0, medir(b"basura"))
        assert q.estado.startswith("no medible: ") and all(v is None for capa in CAPAS for k, v in q.capas[capa].items() if k != "en_el_rango")

    @pytest.mark.parametrize("argumentos", [("1", 0.0, 0.0), (True, 0.0, 0.0), (1, -5.0, None), (1, "100", None), (1, 100.0, "100"), (1, float("nan"), None)])
    def test_los_argumentos_mal_dados_son_un_error_de_quien_llama(self, argumentos):
        with pytest.raises(ValueError):
            _cd().pieza_de_calibracion(*argumentos, medir(gen.pieza_uniforme().datos))
        with pytest.raises(ValueError):
            _cd().pieza_de_calibracion(1, 0.0, 0.0, "no es una medida")

    @pytest.mark.parametrize("texto,esperado", [("el 99.98 % del fondo está en el blanco máximo", 0.9998), ("el 12.50 % del fondo está en el blanco máximo: revise la tapa, el vidrio o los ajustes (quitar fondo, brillo)", 0.125),
                                                ("no se ve fondo del escáner; no se juzga", None)])
    def test_el_fondo_se_lee_de_la_prueba_c3(self, texto, esperado):
        prueba = _pel().PruebaDeLaVirgen("C3 fondo", "ok", texto)
        assert _cd().fondo_blanco_de((prueba,)) == (None if esperado is None else pytest.approx(esperado, abs=1e-12))

    def test_un_texto_del_fondo_que_no_se_conoce_es_un_error(self):
        with pytest.raises(ValueError, match="C3 fondo"):
            _cd().fondo_blanco_de((_pel().PruebaDeLaVirgen("C3 fondo", "ok", "el fondo es 99.98 % blanco"),))


# ===================================================================================================== (9) las 21 piezas reales de H9

def _faltan_las_piezas(monkeypatch, raiz):
    monkeypatch.setattr(_corpus, "PIEZAS_DE_CALIBRACION_RAIZ", str(raiz))
    return _corpus.piezas_de_calibracion_que_faltan()


class TestLaReglaDePR0DeLasPiezas:
    def test_sin_la_carpeta_no_hay_corpus(self, tmp_path, monkeypatch):
        assert _faltan_las_piezas(monkeypatch, tmp_path / "no_existe") is None

    def test_si_la_carpeta_existe_nombra_las_que_faltan(self, tmp_path, monkeypatch):
        for dosis, archivo in _corpus.PIEZAS_DE_CALIBRACION.items():
            if dosis not in (50, 700):
                (tmp_path / archivo).write_bytes(b"x")
        (tmp_path / "700.tif").mkdir()
        assert _faltan_las_piezas(monkeypatch, tmp_path) == [50, 700]
        (tmp_path / "50.tif").write_bytes(b"")
        assert _faltan_las_piezas(monkeypatch, tmp_path) == [50, 700], "un archivo de 0 bytes y una carpeta no cuentan"

    def test_el_registro_son_las_21_y_la_medida_independiente_las_trae_todas(self):
        assert sorted(_corpus.PIEZAS_DE_CALIBRACION) == [5, 50] + list(range(100, 1001, 50))
        assert set(_corpus.MEDIA_DE_LAS_PIEZAS_22_10) == set(_corpus.PIEZAS_DE_CALIBRACION) == set(NETOD_DE_H9_22_10) | {5}
        assert not set(_corpus.PIEZAS_DE_CALIBRACION.values()) & set(_corpus.peliculas_vigiladas_por_pr0().values()), "registro aparte de las peliculas"


@pytest.fixture(scope="module")
def h9():
    """Las 21 piezas reales: si la carpeta esta, tienen que estar las 21 (si falta una, FALLA nombrandola: PR.0); si no esta, salta (HI-0). Dosis medida = la nominal (P14)."""
    faltan = _corpus.piezas_de_calibracion_que_faltan()
    if faltan is None:
        pytest.skip(f"HI-0: no esta {_corpus.PIEZAS_DE_CALIBRACION_RAIZ}")
    assert not faltan, f"faltan piezas de calibracion en {_corpus.PIEZAS_DE_CALIBRACION_RAIZ}: {faltan}"
    piezas = []
    for k, dosis in enumerate(sorted(_corpus.PIEZAS_DE_CALIBRACION)):
        datos = Path(_corpus.ruta_de_pieza_de_calibracion(dosis)).read_bytes()
        piezas.append(_cd().pieza_de_calibracion(k + 1, float(dosis), float(dosis), medir(datos, _corpus.PIEZAS_DE_CALIBRACION[dosis])))
    return _cd().ajustar(piezas)


class TestLas21PiezasRealesDeH9:
    def test_el_valor_de_cada_pieza_es_la_medida_independiente_del_22_10(self, h9):
        assert len(h9.piezas) == 21
        for q in h9.piezas:
            for k, capa in enumerate(LAS_TRES):
                assert abs(q.capas[capa]["valor"] - _corpus.MEDIA_DE_LAS_PIEZAS_22_10[int(q.dosis_nominal_cgy)][k]) <= 0.1, (q.dosis_nominal_cgy, capa)

    def test_su_netod_contra_la_de_5_cgy_es_la_del_22_10(self, h9):
        assert h9.cero["fuente"] == "pieza_de_menor_dosis" and h9.cero["dosis_cgy"] == 5.0, "la de 5 cGy hace de cero: la curva queda corrida unos 5 cGy (P14)"
        for q in h9.piezas:
            if q.dosis_nominal_cgy > 5:
                for k, capa in enumerate(LAS_TRES):
                    assert abs(q.capas[capa]["netod"] - NETOD_DE_H9_22_10[int(q.dosis_nominal_cgy)][k]) <= 5e-4, (q.dosis_nominal_cgy, capa)
                    assert q.capas[capa]["dosis_cgy"] == q.dosis_nominal_cgy - 5.0

    def test_cada_capa_se_ajusta_y_se_informa_tal_cual_sale(self, h9):
        for capa in CAPAS:
            assert h9.capas[capa]["parametros"] is not None, capa
            assert h9.estado(capa) != VALIDA, "una curva cuyo cero es la pieza de menor dosis nunca es valida (DC3)"
        assert {k: h9.estado(k) for k in CAPAS} == H9_ESTADOS
        assert {k: h9.rango(k) for k in CAPAS} == H9_RANGOS

    def test_ninguna_capa_esta_recortada_y_no_hay_avisos(self, h9):
        assert h9.avisos == () and all(q.capas[c]["recortada"] is None for q in h9.piezas for c in CAPAS)

    def test_la_copia_de_h9_da_lo_mismo(self, h9):
        texto = json.dumps(h9.como_dict(), allow_nan=False, sort_keys=True)
        assert json.dumps(_cd().curva_desde_dict(json.loads(texto)).como_dict(), allow_nan=False, sort_keys=True) == texto


# ===================================================================================================== (10) la copia guardada

class TestLaCopiaGuardada:
    def test_ida_y_vuelta(self, grande):
        d = grande.como_dict()
        texto = json.dumps(d, allow_nan=False)
        c = _cd().curva_desde_dict(json.loads(texto))
        assert c.como_dict() == json.loads(texto)
        for capa in CAPAS:
            assert c.estado(capa) == grande.estado(capa) and c.rango(capa) == grande.rango(capa)
            for x in (0.0, 0.1, 0.3):
                assert c.dosis(capa, x) == grande.dosis(capa, x) and c.netod(capa, grande.dosis(capa, x)) == grande.netod(capa, grande.dosis(capa, x))
                assert c.incertidumbre(capa, x, 0.003) == grande.incertidumbre(capa, x, 0.003)
        assert all(q.medida is None for q in c.piezas) and all(q.medida is not None for q in grande.piezas)

    def test_ajustar_las_piezas_de_la_copia_da_la_misma_curva(self, grande):
        """CD.4 (`recalcular`) reajusta desde lo medido guardado, sin los escaneos: las piezas de la copia llevan todo lo que el ajuste necesita (el valor, su u, el recorte, la posicion, el fondo y la
        cadena de captura)."""
        copia = _cd().curva_desde_dict(json.loads(json.dumps(grande.como_dict())))
        assert all(q.cadena == {"equipo": None, "bits": 8, "dpi": 150.0, "formato": "TIFF"} for q in copia.piezas)
        assert _cd().ajustar(copia.piezas).como_dict() == grande.como_dict()

    def test_la_curva_sin_cero_tambien(self):
        c = _cd().ajustar([])
        assert _cd().curva_desde_dict(json.loads(json.dumps(c.como_dict()))).como_dict() == c.como_dict()


def _danada(d, ruta, valor=None, quitar=False):
    d = copy.deepcopy(d)
    contenedor = d
    for clave in ruta[:-1]:
        contenedor = contenedor[clave]
    if quitar:
        del contenedor[ruta[-1]]
    else:
        contenedor[ruta[-1]] = valor
    return d


def _anidada(niveles):
    v = 1
    for _ in range(niveles):
        v = {"x": v}
    return v


DANADAS = [
    ("no_es_dict", lambda d: [d], "La curva de dosis debe ser un diccionario."),
    ("otra_version", lambda d: _danada(d, ["version"], "CD-0"), "es de la versión 'CD-0'"),
    ("sin_version", lambda d: _danada(d, ["version"], quitar=True), "es de la versión None"),
    ("otro_modelo", lambda d: _danada(d, ["modelo"], "polinomio"), "es del modelo 'polinomio'"),
    ("falta_capas", lambda d: _danada(d, ["capas"], quitar=True), "la curva no trae exactamente sus claves"),
    ("clave_de_mas", lambda d: {**d, "otra": 1}, "la curva no trae exactamente sus claves"),
    ("avisos_none", lambda d: _danada(d, ["avisos"], None), "los avisos no son una lista de textos"),
    ("aviso_numero", lambda d: _danada(d, ["avisos"], [3]), "los avisos no son una lista de textos"),
    ("parametros_lista", lambda d: _danada(d, ["parametros"], []), "los parámetros no son un diccionario"),
    ("parametros_profundos", lambda d: _danada(d, ["parametros"], _anidada(12)), "los parámetros anidan demasiados niveles"),
    ("cadena_profunda", lambda d: _danada(d, ["cadena"], _anidada(12)), "la cadena de captura anidan demasiados niveles"),
    ("u_dosis_texto", lambda d: _danada(d, ["u_dosis_medida_pct"], "2"), "la incertidumbre de la dosis medida no es un número de 0 o más"),
    ("u_dosis_negativa", lambda d: _danada(d, ["u_dosis_medida_pct"], -1.0), "la incertidumbre de la dosis medida no es un número de 0 o más"),
    ("cero_otra_fuente", lambda d: _danada(d, ["cero", "fuente"], "el_aire"), "la fuente del cero no es una de"),
    ("cero_i0_nan", lambda d: _danada(d, ["cero", "capas", "G", "i0"], float("nan")), "el I0 o su u de la capa G no son números válidos"),
    ("cero_i0_cero", lambda d: _danada(d, ["cero", "capas", "R", "i0"], 0.0), "el I0 o su u de la capa R no son números válidos"),
    ("cero_sin_gris", lambda d: _danada(d, ["cero", "capas", "gris"], quitar=True), "las capas del cero no trae exactamente sus claves"),
    ("capa_de_menos", lambda d: _danada(d, ["capas", "B"], quitar=True), "las capas no trae exactamente sus claves"),
    ("estado_numero", lambda d: _danada(d, ["capas", "G", "estado"], 1), "el estado de la capa G no es un texto"),
    ("a_negativo", lambda d: _danada(d, ["capas", "G", "parametros", "a"], -1.0), "los parámetros de la capa G no son los de una curva monótona por el origen"),
    ("n_cinco", lambda d: _danada(d, ["capas", "R", "parametros", "n"], 5.0), "los parámetros de la capa R no son los de una curva monótona por el origen"),
    ("n_cero", lambda d: _danada(d, ["capas", "R", "parametros", "n"], 0.5), "los parámetros de la capa R no son los de una curva monótona por el origen"),
    ("b_booleano", lambda d: _danada(d, ["capas", "B", "parametros", "b"], True), "los parámetros de la capa B no son números"),
    ("b_infinito", lambda d: _danada(d, ["capas", "B", "parametros", "b"], float("inf")), "los parámetros de la capa B no son números"),
    ("parametros_sin_n", lambda d: _danada(d, ["capas", "G", "parametros", "n"], quitar=True), "los parámetros de la capa G no trae exactamente sus claves"),
    ("rango_negativo", lambda d: _danada(d, ["capas", "G", "rango_cgy"], -10.0), "rango_cgy de la capa G no es un número de 0 o más"),
    ("valida_sin_parametros", lambda d: _danada(_danada(d, ["capas", "G", "parametros"], None), ["capas", "G", "rango_cgy"], None), "la capa G es «válida» sin parámetros o sin rango útil"),
    ("dosis_en_el_rango_decimal", lambda d: _danada(d, ["capas", "G", "dosis_en_el_rango"], 10.0), "las dosis en el rango de la capa G no son un entero de 0 o más"),
    ("pieza_sin_orden", lambda d: _danada(d, ["piezas", 0, "orden"], quitar=True), "la pieza 1 de la lista no trae exactamente sus claves"),
    ("pieza_netod_texto", lambda d: _danada(d, ["piezas", 3, "capas", "G", "netod"], "0.2"), "un valor de la capa G de la pieza 4 de la lista no es un número"),
    ("pieza_en_rango_numero", lambda d: _danada(d, ["piezas", 3, "capas", "R", "en_el_rango"], 1), "un valor de la capa R de la pieza 4 de la lista no es un número"),
    ("pieza_fondo_fuera", lambda d: _danada(d, ["piezas", 2, "fondo_blanco"], 1.5), "el fondo blanco de la pieza 3 de la lista no es una fracción"),
    ("piezas_no_lista", lambda d: _danada(d, ["piezas"], {}), "las piezas no son una lista"),
    ("pieza_cadena_sin_bits", lambda d: _danada(d, ["piezas", 0, "cadena", "bits"], quitar=True), "la cadena de captura de la pieza 1 de la lista no trae exactamente sus claves"),
    # ---- (29-10, el implementador) las 16 validaciones que la bateria de mutaciones mostro sin forma danada que las ejerza: quitada cualquiera de ellas, la copia danada entraba
    ("cadena_texto", lambda d: _danada(d, ["cadena"], "una cadena"), "la cadena de captura no es un diccionario"),
    ("cero_sin_detalle", lambda d: _danada(d, ["cero", "detalle"], quitar=True), "el cero no trae exactamente sus claves"),
    ("cero_detalle_numero", lambda d: _danada(d, ["cero", "detalle"], 5), "el detalle del cero no es un texto"),
    ("cero_dosis_negativa", lambda d: _danada(d, ["cero", "dosis_cgy"], -1.0), "la dosis del cero no es un número de 0 o más"),
    ("cero_capa_sin_u", lambda d: _danada(d, ["cero", "capas", "G", "u_i0"], quitar=True), "el cero de la capa G no trae exactamente sus claves"),
    ("capa_con_clave_de_mas", lambda d: _danada(d, ["capas", "G", "otra"], 1), "la capa G no trae exactamente sus claves"),
    ("limite_numero", lambda d: _danada(d, ["capas", "G", "limite"], 5), "el límite de la capa G no es un texto"),
    ("rango_sin_parametros", lambda d: _danada(_danada(d, ["capas", "G", "parametros"], None), ["capas", "G", "estado"], "incompleta: quedan 0 dosis en el rango útil (hacen falta 6)"),
     "la capa G trae rango útil sin parámetros"),
    ("pieza_orden_texto", lambda d: _danada(d, ["piezas", 0, "orden"], "1"), "el orden de la pieza 1 de la lista no es un entero"),
    ("pieza_nominal_negativa", lambda d: _danada(d, ["piezas", 1, "dosis_nominal_cgy"], -5.0), "la dosis nominal de la pieza 2 de la lista no es un número de 0 o más"),
    ("pieza_medida_texto", lambda d: _danada(d, ["piezas", 1, "dosis_medida_cgy"], "50"), "la dosis medida de la pieza 2 de la lista no es un número"),
    ("pieza_archivo_numero", lambda d: _danada(d, ["piezas", 0, "archivo"], 3), "el estado, el archivo o la huella de la pieza 1 de la lista no son textos"),
    ("pieza_sin_capa_gris", lambda d: _danada(d, ["piezas", 0, "capas", "gris"], quitar=True), "las capas de la pieza 1 de la lista no trae exactamente sus claves"),
    ("pieza_capa_con_clave_de_mas", lambda d: _danada(d, ["piezas", 0, "capas", "G", "otra"], 1), "la capa G de la pieza 1 de la lista no trae exactamente sus claves"),
    ("pieza_posicion_sin_y", lambda d: _danada(d, ["piezas", 0, "posicion_mm", "y"], quitar=True), "la posición de la pieza 1 de la lista no trae exactamente sus claves"),
    ("pieza_posicion_texto", lambda d: _danada(d, ["piezas", 0, "posicion_mm", "x"], "izquierda"), "la posición de la pieza 1 de la lista no son números"),
    # ---- (30-10, CD3-REV1-03, ronda 1 de la revision) la cadena de captura de cada pieza y de la curva con sus claves, sus tipos y el tope de profundidad de lo libre, y la pieza «ok» con su valor y su u: antes
    # se aceptaban y `ajustar(copia.piezas)` (CD.4) lanzaba lejos de donde se habia leido la copia
    ("pieza_cadena_bits_texto", lambda d: _danada(d, ["piezas", 3, "cadena", "bits"], "8"), "la cadena de captura de la pieza 4 de la lista " + CADENA_MAL_TIPADA),
    ("pieza_cadena_bits_booleano", lambda d: _danada(d, ["piezas", 3, "cadena", "bits"], True), "la cadena de captura de la pieza 4 de la lista " + CADENA_MAL_TIPADA),
    ("pieza_cadena_bits_cero", lambda d: _danada(d, ["piezas", 3, "cadena", "bits"], 0), "la cadena de captura de la pieza 4 de la lista " + CADENA_MAL_TIPADA),
    ("pieza_cadena_dpi_texto", lambda d: _danada(d, ["piezas", 3, "cadena", "dpi"], "150"), "la cadena de captura de la pieza 4 de la lista " + CADENA_MAL_TIPADA),
    ("pieza_cadena_dpi_lista", lambda d: _danada(d, ["piezas", 3, "cadena", "dpi"], [1, 2]), "la cadena de captura de la pieza 4 de la lista " + CADENA_MAL_TIPADA),
    ("pieza_cadena_dpi_negativa", lambda d: _danada(d, ["piezas", 3, "cadena", "dpi"], -150.0), "la cadena de captura de la pieza 4 de la lista " + CADENA_MAL_TIPADA),
    ("pieza_cadena_equipo_numero", lambda d: _danada(d, ["piezas", 3, "cadena", "equipo"], 5), "la cadena de captura de la pieza 4 de la lista " + CADENA_MAL_TIPADA),
    ("pieza_cadena_formato_dict", lambda d: _danada(d, ["piezas", 3, "cadena", "formato"], {"x": 1}), "la cadena de captura de la pieza 4 de la lista " + CADENA_MAL_TIPADA),
    ("pieza_cadena_profunda", lambda d: _danada(d, ["piezas", 3, "cadena", "equipo"], _anidada(12)), "la cadena de captura de la pieza 4 de la lista anida demasiados niveles"),
    ("pieza_cadena_muy_profunda", lambda d: _danada(d, ["piezas", 3, "cadena", "equipo"], _anidada(450)), "la cadena de captura de la pieza 4 de la lista anida demasiados niveles"),
    ("cadena_de_la_curva_sin_dpi", lambda d: _danada(d, ["cadena", "dpi"], quitar=True), "la cadena de captura no trae exactamente sus claves"),
    ("cadena_de_la_curva_dpi_texto", lambda d: _danada(d, ["cadena", "dpi"], "150"), "la cadena de captura " + CADENA_MAL_TIPADA),
    ("pieza_ok_sin_valor", lambda d: _danada(d, ["piezas", 0, "capas", "G", "valor"], None), "la capa G de la pieza 1 de la lista " + OK_SIN_VALOR),
    ("pieza_ok_sin_u", lambda d: _danada(d, ["piezas", 3, "capas", "R", "u"], None), "la capa R de la pieza 4 de la lista " + OK_SIN_VALOR),
    ("pieza_ok_valor_negativo", lambda d: _danada(d, ["piezas", 3, "capas", "B", "valor"], -1.0), "la capa B de la pieza 4 de la lista " + OK_SIN_VALOR),
    ("pieza_ok_u_negativa", lambda d: _danada(d, ["piezas", 3, "capas", "gris", "u"], -0.5), "la capa gris de la pieza 4 de la lista " + OK_SIN_VALOR),
]


class TestLasCopiasDanadas:
    def test_son_treinta_o_mas(self):
        assert len(DANADAS) >= 30 and len({nombre for nombre, _, _ in DANADAS}) == len(DANADAS)

    @pytest.mark.parametrize("nombre,danar,motivo", DANADAS, ids=[n for n, _, _ in DANADAS])
    def test_se_rechaza_con_su_motivo(self, grande, nombre, danar, motivo):
        with pytest.raises(ValueError) as e:
            _cd().curva_desde_dict(danar(grande.como_dict()))
        assert motivo in str(e.value), str(e.value)


# ===================================================================================================== (11) los parametros y la estructura

class TestLosParametros:
    def test_los_del_bloque_con_su_valor_su_unidad_y_su_motivo(self):
        cd = _cd()
        esperados = {"piezas_minimas": 6, "residuo_maximo_pct": 3.0, "residuo_maximo_bajas_pct": 5.0, "dosis_baja_cgy": 100.0, "resolucion_maxima_pct": 3.0, "separacion_minima_u": 2.0,
                     "modelo": "devic", "version": "CD-1", "distancia_en_el_vidrio_mm": 20.0, "diferencia_de_fondo_blanco": 0.005}
        assert {k: v["valor"] for k, v in cd.PARAMETROS_DE_LA_CURVA.items()} == esperados
        assert all(set(v) == {"valor", "unidad", "motivo"} and v["unidad"] and len(v["motivo"]) > 40 for v in cd.PARAMETROS_DE_LA_CURVA.values())
        assert cd.VALORES_DE_LA_CURVA == esperados and cd.VERSION_CURVA == "CD-1" and cd.MODELO_DEVIC == "devic"

    def test_la_curva_lleva_los_parametros_con_que_se_ajusto(self, grande):
        assert grande.parametros == _cd().VALORES_DE_LA_CURVA and grande.version == "CD-1" and grande.modelo == "devic"


class TestLaEstructura:
    def _arbol(self):
        return ast.parse((RAIZ / "analisisImagenes" / "curva_dosis.py").read_text(encoding="utf-8"))

    def test_sin_qt_ni_base_y_scipy_arriba(self):
        arbol = self._arbol()
        arriba = [n for n in arbol.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        raices = {a.name.split(".")[0] for n in arriba if isinstance(n, ast.Import) for a in n.names} | {(n.module or "").split(".")[0] for n in arriba if isinstance(n, ast.ImportFrom)}
        assert raices == {"math", "dataclasses", "numpy", "scipy", "analisisImagenes"}, raices
        assert any(isinstance(n, ast.ImportFrom) and n.module == "scipy.optimize" for n in arriba), "scipy.optimize se importa arriba: PyInstaller solo empaqueta lo que ve importado"
        dentro = [n for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef) for n in ast.walk(f) if isinstance(n, (ast.Import, ast.ImportFrom))]
        assert not dentro, "ningun import dentro de una funcion"

    def test_el_motor_de_la_pelicula_es_el_de_cd2(self):
        arbol = self._arbol()
        desde = [n for n in arbol.body if isinstance(n, ast.ImportFrom) and n.module == "analisisImagenes.pelicula"]
        assert len(desde) == 1 and {"MedidaDePieza", "ReferenciaVirgen", "CAPAS_DEL_PISO"} <= {a.name for a in desde[0].names}
        llamadas = {n.func.id for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert not {"leer_pelicula", "medir_pieza_uniforme", "piso_de_pelicula_virgen"} & llamadas, "la curva no mide: recibe la medida de CD.2"

    def test_scipy_esta_declarado_en_requirements(self):
        lineas = (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
        assert any(linea.strip().lower().startswith("scipy==") for linea in lineas)

    def test_la_curva_y_la_pieza_son_congeladas(self):
        cd = _cd()
        for clase in (cd.CurvaDeDosis, cd.PiezaDeCalibracion):
            assert clase.__dataclass_params__.frozen


# ===================================================================================================== (12) ampliacion del implementador (29-10): lo que la bateria de mutaciones mostro sin guardia
#
# La prueba de referencia del pre-vuelo (104 casos) dejaba caer las 29 mutaciones de las pistas; el implementador escribio 87 mas (`borradores/CD3/mutaciones_extra_CD3.json` del anexo) y 38 SOBREVIVIAN. Estas son las
# pruebas que matan las que no son equivalentes (las equivalentes estan declaradas en `borradores/CD3/obstaculos.md`): cada una fija una regla que el bloque o las pistas declaran y que solo H9, o nadie, vigilaba.

def a_mano(orden, nominal, medida, valor, u, recortada=None, posicion=None, fondo=None):
    """Una `PiezaDeCalibracion` armada con numeros EXACTOS, sin imagen y con el mismo `valor`, `u` y `recortada` en las cuatro capas (y, si se dan, su `posicion` {"x", "y"} en mm y su `fondo` en el blanco
    maximo): fija una regla de la curva sin que el ruido de una pieza real la esconda."""
    capas = {c: {"valor": float(valor), "u": float(u), "recortada": recortada, "netod": None, "u_netod": None, "dosis_cgy": None, "residuo_pct": None, "en_el_rango": False} for c in CAPAS}
    return _cd().PiezaDeCalibracion(orden, float(nominal), None if medida is None else float(medida), "ok", capas, posicion, fondo, f"{nominal:g}.tif", None,
                                    {"equipo": None, "bits": 8, "dpi": 150.0, "formato": "TIFF"})


def por_netod(dosis, netods, i0=200.0, u_relativa=0.001, u_del_cero=0.2):
    """El cero (orden 1: valor `i0` y u `u_del_cero`) y una pieza por dosis cuya netOD contra ese cero es la dada: valor = i0 · 10^(−x), con la u relativa `u_relativa`."""
    piezas = [a_mano(1, 0, 0.0, i0, u_del_cero)]
    for k, (d, x) in enumerate(zip(dosis, netods)):
        valor = i0 * 10.0 ** (-x)
        piezas.append(a_mano(k + 2, d, d, valor, valor * u_relativa))
    return piezas


DOSIS_DE_LA_SEPARACION = (50, 100, 150, 200, 250, 300, 350, 400)
UMBRAL_DE_LA_SEPARACION = 2 * math.sqrt(0.001 ** 2 + 0.001 ** 2) / math.log(10)            # 2 u de la diferencia de dos medidas de u relativa 0.001: 0.001228 de netOD


class TestLaSeparacionDeLasDosis:
    """(b) de DC5: una dosis cuenta si su netOD supera a la de la anterior en MAS de 2 u (la u de esa diferencia; la primera, contra el cero). Con piezas armadas a mano la frontera se prueba de los dos lados."""

    @pytest.mark.parametrize("subida,se_distingue", [(0.9 * UMBRAL_DE_LA_SEPARACION, False), (1.1 * UMBRAL_DE_LA_SEPARACION, True)])
    def test_la_frontera_es_de_dos_u(self, subida, se_distingue):
        netods = [0.0100, 0.0200, 0.0300, 0.0300 + subida] + [0.0400 + subida + 0.0100 * k for k in range(4)]
        c = _cd().ajustar(por_netod(DOSIS_DE_LA_SEPARACION, netods))
        for capa in CAPAS:
            if se_distingue:
                assert c.capas[capa]["dosis_en_el_rango"] == 8 and c.rango(capa) == 400.0 and c.capas[capa]["limite"] is None, (capa, c.capas[capa]["limite"])
            else:
                assert c.capas[capa]["dosis_en_el_rango"] == 3 and c.rango(capa) == 150.0, capa
                assert c.capas[capa]["limite"] == f"la pieza de 200 cGy no se distingue de la de 150 cGy: su netOD sube {subida:.4f} y hacen falta más de 2 u ({UMBRAL_DE_LA_SEPARACION:.4f})"
                assert c.estado(capa) == POCAS.format(n=3)

    def test_la_u_del_cero_cuenta_en_la_primera_dosis(self):
        """La primera dosis se mide contra el cero: si el cero tiene 1 % de incertidumbre (u = 2 sobre I0 = 200), 0.006 de netOD no la separa de el."""
        netods = [0.006 + 0.0100 * k for k in range(8)]
        umbral = 2 * math.sqrt(0.01 ** 2 + 0.001 ** 2) / math.log(10)                                 # 0.0087
        c = _cd().ajustar(por_netod(DOSIS_DE_LA_SEPARACION, netods, u_del_cero=2.0))
        for capa in CAPAS:
            assert c.capas[capa]["dosis_en_el_rango"] == 0 and c.rango(capa) is None, capa
            assert c.capas[capa]["limite"] == f"la pieza de 50 cGy no se distingue de la de 0 cGy: su netOD sube 0.0060 y hacen falta más de 2 u ({umbral:.4f})"
        sin_incertidumbre = _cd().ajustar(por_netod(DOSIS_DE_LA_SEPARACION, netods, u_del_cero=0.2))
        assert all(sin_incertidumbre.capas[capa]["dosis_en_el_rango"] > 0 for capa in CAPAS), "con la u del cero de 0.1 % las mismas piezas si se separan del cero"

    def test_los_parametros_cambian_la_frontera(self):
        subida = 0.9 * UMBRAL_DE_LA_SEPARACION
        netods = [0.0100, 0.0200, 0.0300, 0.0300 + subida] + [0.0400 + subida + 0.0100 * k for k in range(4)]
        c = _cd().ajustar(por_netod(DOSIS_DE_LA_SEPARACION, netods), {"separacion_minima_u": 1.0})
        assert all(c.capas[capa]["dosis_en_el_rango"] == 8 for capa in CAPAS), "con 1 u la misma subida (0.9 de las 2 u) ya separa las dosis"
        assert c.parametros["separacion_minima_u"] == 1.0


class TestLasReplicasDeUnaDosis:
    def test_el_rango_termina_en_la_media_de_las_piezas_de_la_ultima_dosis(self):
        """La ultima dosis tiene dos piezas medidas en 400 y 410 cGy: su netOD es la media de las dos y el rango termina en la dosis media, 405 (CD3-D6)."""
        r = DEVIC[1]
        piezas = [a_mano(1, 0, 0.0, 200.0, 0.1)]
        for orden, (nominal, medida) in enumerate([(d, d) for d in (50, 100, 150, 200, 300, 400)] + [(400, 410)], start=2):
            valor = 200.0 * 10.0 ** (-r.netod(medida))
            piezas.append(a_mano(orden, nominal, medida, valor, valor * 0.0005))
        c = _cd().ajustar(piezas)
        for capa in CAPAS:
            assert c.estado(capa) == VALIDA and c.capas[capa]["dosis_en_el_rango"] == 6, (capa, c.estado(capa))
            assert c.rango(capa) == pytest.approx(405.0, abs=1e-9)
            assert c.capas[capa]["netod_maxima"] == pytest.approx((r.netod(400.0) + r.netod(410.0)) / 2, rel=1e-9)


class TestLaToleranciaDeLasDosisBajas:
    def test_por_debajo_de_100_cgy_es_estrictamente_por_debajo(self, grande):
        """La tolerancia de ±5 % vale POR DEBAJO de 100 cGy: una pieza de exactamente 100 cGy ya se juzga con la de ±3 % (aqui 0 %, para que el ruido de la pieza la nombre)."""
        c = _cd().ajustar(grande.piezas, {"residuo_maximo_pct": 0.0, "residuo_maximo_bajas_pct": 1000.0})
        for capa in CAPAS:
            assert c.estado(capa).startswith("no válida: el residuo de la pieza de 100 cGy es "), (capa, c.estado(capa))


class TestLosEstadosEnLosBordes:
    def test_la_dosis_que_falta_nombra_la_primera_fila_y_pesa_mas_que_otra_cadena(self, grande):
        sin = [q if q.orden not in (3, 5) else _cd().pieza_de_calibracion(q.orden, q.dosis_nominal_cgy, None, q.medida) for q in grande.piezas]
        c = _cd().ajustar(list(reversed(sin)))
        assert all(c.estado(capa) == FALTA_DOSIS.format(orden=3, nominal=100) for capa in CAPAS), "la primera fila del formulario, vengan las piezas en el orden que vengan"
        otra = [q if q.orden != 7 else dataclasses.replace(q, cadena={**q.cadena, "bits": 16}) for q in sin]
        c = _cd().ajustar(otra)
        assert all(c.estado(capa) == FALTA_DOSIS.format(orden=3, nominal=100) for capa in CAPAS), "lo incompleto pesa mas que la otra cadena (CD3-D4: incompleta, no valida, guia, valida)"

    def test_con_menos_de_tres_piezas_no_se_ajusta(self, grande):
        c = _cd().ajustar([q for q in grande.piezas if q.dosis_nominal_cgy in (0.0, 100.0, 400.0)])
        for capa in CAPAS:
            assert c.capas[capa]["parametros"] is None and c.rango(capa) is None and c.capas[capa]["dosis_en_el_rango"] == 0, capa
            assert c.estado(capa) == POCAS.format(n=0)
            with pytest.raises(ValueError, match="no tiene curva"):
                c.dosis(capa, 0.1)

    def test_una_pieza_fuera_del_rango_trae_igual_su_residuo(self):
        """Fuera del rango util la curva ya no se garantiza, pero el residuo de la pieza se informa: dice cuanto se aparta la curva de ella."""
        c = _cd().ajustar(calibracion(lado_mm=GRANDE, negro_desde_cgy={"R": 400}))
        p = c.capas["R"]["parametros"]
        fuera = [q for q in c.piezas if q.dosis_nominal_cgy >= 400]
        assert len(fuera) == 5 and all(not q.capas["R"]["en_el_rango"] for q in fuera)
        for q in fuera:
            esperado = 100 * (devic(q.capas["R"]["netod"], p["a"], p["b"], p["n"]) - q.capas["R"]["dosis_cgy"]) / q.capas["R"]["dosis_cgy"]
            assert q.capas["R"]["residuo_pct"] == pytest.approx(esperado, rel=1e-9)

    def test_una_virgen_rechazada_no_hace_de_cero_y_se_avisa(self, grande):
        mala = _pel().piso_de_pelicula_virgen(b"no es una imagen", _P(), "virgen.tif", FECHA)
        assert mala.estado != "ok"
        c = _cd().ajustar([q for q in grande.piezas if q.dosis_nominal_cgy > 0], virgen=mala)
        assert c.cero["fuente"] == "pieza_de_menor_dosis"
        assert f"la película virgen montada no sirve de cero: {mala.estado}" in c.avisos

    def test_sin_ninguna_pieza_medible_la_virgen_montada_tampoco_hace_de_cero(self):
        """Sin una pieza medible no hay cadena de captura con que comparar la virgen: no sirve de cero, se avisa, y la curva sigue sin cero (el estado de siempre)."""
        piezas = [_cd().pieza_de_calibracion(k + 1, float(d), float(d), medir(b"no es una imagen", f"{d}.tif")) for k, d in enumerate((0, 100, 200))]
        c = _cd().ajustar(piezas, virgen=_virgen())
        assert c.cero is None and all(c.estado(capa) == SIN_CERO for capa in CAPAS)
        assert any(a.startswith("la película virgen montada no sirve de cero: se escaneó con otra cadena de captura (") for a in c.avisos), c.avisos


class TestElCeroDeMenorDosis:
    def test_es_la_pieza_de_menor_dosis_MEDIDA_y_las_demas_se_cuentan_desde_ella(self, grande):
        """La de 50 cGy nominales se midio en 52 y la de 100 en 47: la de menor dosis MEDIDA (la verdad de la camara) es la de 100, y las demas se cuentan desde sus 47 cGy."""
        medidas = {2: 52.0, 3: 47.0}
        piezas = [_cd().pieza_de_calibracion(q.orden, q.dosis_nominal_cgy, medidas.get(q.orden, q.dosis_medida_cgy), q.medida) for q in grande.piezas if q.dosis_nominal_cgy > 0]
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and c.cero["dosis_cgy"] == 47.0 and "la pieza 3 (100 cGy" in c.cero["detalle"], c.cero
        por_orden = {q.orden: q for q in c.piezas}
        assert por_orden[2].capas["G"]["dosis_cgy"] == 5.0 and por_orden[4].capas["G"]["dosis_cgy"] == 150.0 - 47.0


@pytest.fixture(scope="module")
def una_medida():
    return medir(gen.pieza_de_dosis(200, DEVIC, lado_mm=18.0).datos, "200.tif")


class TestLaCadenaDeCapturaDeUnaPieza:
    @pytest.mark.parametrize("campo,otro", [("equipo", "EPSON Expression 12000XL"), ("bits", 16), ("dpi_declarado", 600.0), ("formato", "JPEG")])
    def test_cada_campo_la_distingue(self, una_medida, campo, otro):
        cd = _cd()
        otra = dataclasses.replace(una_medida, procedencia={**una_medida.procedencia, campo: otro})
        assert set(cd.cadena_de_captura(una_medida.procedencia)) == {"equipo", "bits", "dpi", "formato"}
        assert cd.cadena_de_captura(otra.procedencia) != cd.cadena_de_captura(una_medida.procedencia)
        assert cd.pieza_de_calibracion(1, 200.0, 200.0, otra).cadena != cd.pieza_de_calibracion(1, 200.0, 200.0, una_medida).cadena


class TestLosArgumentosDeAjustar:
    def test_las_piezas_y_la_virgen_mal_dadas_son_un_error_de_quien_llama(self):
        with pytest.raises(ValueError, match="PiezaDeCalibracion"):
            _cd().ajustar([1, 2])
        with pytest.raises(ValueError, match="ReferenciaVirgen"):
            _cd().ajustar([], virgen="no es una referencia")


class TestLosAvisosEnLaFrontera:
    """Los dos avisos dicen «mas de»: a EXACTAMENTE el limite no avisan (con piezas armadas a mano, donde el limite es un numero exacto)."""

    def test_la_posicion_es_el_centro_de_la_caja_a_centesimas_de_mm(self):
        q = pieza(2, 200, lado_mm=18.0, pagina_mm=(110.0, 40.0), posicion_mm=(40.0, 10.0))
        caja = q.medida.region["pelicula_mm"]
        assert q.posicion_mm == {"x": round(caja["x"] + caja["ancho"] / 2.0, 2), "y": round(caja["y"] + caja["alto"] / 2.0, 2)} == {"x": 48.95, "y": 18.95}

    def test_a_exactamente_20_mm_no_hay_aviso_del_lugar_del_vidrio_y_a_20_5_si(self):
        piezas = por_netod(DOSIS_DE_LA_SEPARACION, [0.0100 * (k + 1) for k in range(8)])
        for orden, x in ((1, 0.0), (2, 20.0), (3, 20.5)):
            piezas[orden - 1] = dataclasses.replace(piezas[orden - 1], posicion_mm={"x": x, "y": 0.0})
        c = _cd().ajustar(piezas)
        assert len(c.avisos) == 1 and c.avisos[0].startswith(OTRO_LUGAR.format(orden=3, nominal=100)) and "a 20.5 mm del centro del cero (más de 20 mm)" in c.avisos[0], c.avisos

    def test_a_exactamente_la_diferencia_de_fondo_permitida_no_hay_aviso(self):
        """Con la diferencia permitida en 0.5: el fondo de la pieza 2 (0.5) esta a 0.5 del del cero (1.0), justo en el limite; el de la pieza 3 (0.25), a 0.75."""
        piezas = por_netod(DOSIS_DE_LA_SEPARACION, [0.0100 * (k + 1) for k in range(8)])
        for orden, fondo in ((1, 1.0), (2, 0.5), (3, 0.25)):
            piezas[orden - 1] = dataclasses.replace(piezas[orden - 1], fondo_blanco=fondo)
        c = _cd().ajustar(piezas, {"diferencia_de_fondo_blanco": 0.5})
        assert len(c.avisos) == 1 and c.avisos[0].startswith(EXPOSICION.format(orden=3, nominal=100)), c.avisos


class TestLaIncertidumbreDeUnaDosisConReplicas:
    def test_es_la_raiz_de_la_media_de_los_cuadrados_ni_la_media_ni_la_mayor(self):
        """La ultima dosis tiene dos piezas con incertidumbres muy distintas: la de la dosis es la raiz de la media de sus cuadrados (CD3-D6). Con la resolucion maxima entre la que da esa u y la que daria
        la mayor, la dosis se conserva; entre la que da y la que daria la media, se pierde."""
        r = gen.RespuestaLineal(5000.0)
        piezas = [a_mano(1, 0, 0.0, 200.0, 0.1)]
        for orden, (d, u_relativa) in enumerate([(100, 0.0005), (200, 0.0005), (300, 0.0005), (400, 0.0005), (500, 0.0005), (600, 0.0005), (600, 0.0100)], start=2):
            valor = 200.0 * 10.0 ** (-r.netod(d))
            piezas.append(a_mano(orden, d, d, valor, valor * u_relativa))
        c = _cd().ajustar(piezas)
        assert all(c.capas[capa]["dosis_en_el_rango"] == 6 for capa in CAPAS), "con la resolucion de fabrica (3 %) la dosis de 600 cGy se resuelve"
        u = [q.capas["G"]["u_netod"] for q in c.piezas if q.dosis_nominal_cgy == 600]
        rms, media, mayor = math.sqrt(sum(v * v for v in u) / 2), sum(u) / 2, max(u)
        x = r.netod(600.0)
        resolucion = {nombre: 100 * v / x for nombre, v in (("rms", rms), ("media", media), ("mayor", mayor))}              # en una respuesta lineal D' / D = 1 / x
        assert resolucion["media"] < resolucion["rms"] < resolucion["mayor"]
        entre_rms_y_mayor = _cd().ajustar(piezas, {"resolucion_maxima_pct": (resolucion["rms"] + resolucion["mayor"]) / 2})
        entre_media_y_rms = _cd().ajustar(piezas, {"resolucion_maxima_pct": (resolucion["media"] + resolucion["rms"]) / 2})
        assert all(entre_rms_y_mayor.capas[capa]["dosis_en_el_rango"] == 6 for capa in CAPAS)
        assert all(entre_media_y_rms.capas[capa]["dosis_en_el_rango"] == 5 for capa in CAPAS)


# ===================================================================================================== (13) correccion de la ronda 1 de la revision (30-10)
#
# Cuatro hallazgos de la primera ronda de la revision (CD3-REV1-01 a CD3-REV1-04), reproducidos con una corrida real (`logs/CD3/correccion_ronda1/` del anexo) y corregidos en su causa. Las pruebas de la virgen
# angosta, de la cadena de captura y de la pieza del cero caen contra el modulo de antes; las de los avisos con cada fuente del cero pasaban (la produccion ya avisaba: lo que faltaba era la prueba) y las
# guardan las mutaciones RV* de `cd3_mutaciones.py`, que antes sobrevivian a los 141 casos.

def _virgen_de(ancho, alto, pagina=None):
    """Una pelicula virgen sintetica de `ancho` x `alto` mm pegada en (3, 3) mm de una pagina (por omision, 6 mm mas grande que ella), medida como la de OD.1 (600 ppp)."""
    lienzo = gen.Lienzo(*(pagina or (ancho + 6.0, alto + 6.0)), 600.0, semilla=9)
    lienzo.pegar_pelicula(3.0, 3.0, ancho, alto, (152.12, 194.11, 86.77), gen.RUIDO_EPSON179)
    return _pel().piso_de_pelicula_virgen(lienzo.codificar(), _P(), "virgen.tif", FECHA)


@pytest.fixture(scope="module")
def virgen_angosta():
    """11 x 80 mm: «ok» para A.3 (le sobra el area minima a 2 mm de los bordes) y sin sitio para la region central de 10 x 10 mm."""
    return _virgen_de(11.0, 80.0)


class TestUnaVirgenSinSuRegionCentral:
    """CD3-REV1-01. A.3 le pide a una virgen area (400 mm² a 2 mm de los bordes), no que quepan sus regiones de 10 x 10 mm: una virgen angosta es «ok» con `cabe` falso y SIN el ruido de su centro (`ruido` None).
    Sin el no hay incertidumbre del cero (DC2) y `ajustar`, que nunca lanza por el contenido, lanzaba `TypeError`."""

    def test_la_premisa_una_virgen_angosta_es_ok_y_no_trae_la_region_central(self, virgen_angosta):
        tabla = virgen_angosta.uniformidad
        assert virgen_angosta.estado == "ok" and tabla["cabe"] is False and all(tabla["capas"][c]["ruido"] is None for c in CAPAS), (virgen_angosta.estado, tabla["cabe"])

    @pytest.mark.parametrize("de_su_json", [False, True], ids=["recien_medida", "leida_de_su_json"])
    def test_no_hace_de_cero_se_avisa_y_ajustar_no_lanza(self, virgen_angosta, de_su_json):
        virgen = _pel().referencia_virgen_desde_dict(json.loads(json.dumps(virgen_angosta.como_dict()))) if de_su_json else virgen_angosta
        c = _cd().ajustar(calibracion(cero=False, dpi=600.0, lado_mm=18.0), virgen=virgen)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and VIRGEN_SIN_CENTRO in c.avisos, c.avisos
        assert c.estado("G") == GUIA.format(dosis=50), "sin la virgen el cero es la pieza de menor dosis y la curva queda como guia"

    def test_con_el_centro_pero_sin_las_cinco_regiones_si_hace_de_cero_con_el_ruido_de_su_centro(self):
        virgen = _virgen_de(20.0, 80.0)
        tabla = virgen.uniformidad
        assert virgen.estado == "ok" and tabla["cabe"] is False and all(tabla["capas"][c]["ruido"] is not None for c in CAPAS)
        c = _cd().ajustar(calibracion(cero=False, dpi=600.0, lado_mm=18.0), virgen=virgen)
        assert c.cero["fuente"] == "pelicula_virgen" and not any(a.startswith("la película virgen montada no sirve de cero") for a in c.avisos), c.avisos
        for capa in CAPAS:
            assert c.cero["capas"][capa]["i0"] == virgen.valor(capa)
            assert c.cero["capas"][capa]["u_i0"] == pytest.approx(tabla["capas"][capa]["ruido"], rel=1e-12), "la u del cero es el ruido de los pixeles de su centro (DC2)"


@pytest.fixture(scope="module")
def virgen_con_fondo():
    """60 x 60 mm en (3, 3) mm de una pagina de 80 x 80 mm: su centro esta en (33, 33) mm y el 100 % de su fondo esta en el blanco maximo (en una pagina de 66 x 66 no se ve fondo y el aviso del fondo no
    se juzga)."""
    virgen = _virgen_de(60.0, 60.0, pagina=(80.0, 80.0))
    assert virgen.estado == "ok" and virgen.region["pelicula_mm"] == {"x": 3.0, "y": 3.0, "ancho": 60.0, "alto": 60.0}
    assert _cd().fondo_blanco_de(virgen.pruebas) == 1.0
    return virgen


EN_EL_CENTRO_DE_LA_VIRGEN = dict(dpi=600.0, lado_mm=18.0, pagina_mm=(80.0, 60.0), posicion_mm=(24.0, 24.0))          # una pieza de 18 mm con su centro en (33, 33) mm: el de virgen_con_fondo


@pytest.fixture(scope="module")
def en_el_centro():
    """Las diez piezas irradiadas de la plantilla (orden 2 a 11, sin la de 0 cGy), todas con su centro en el de `virgen_con_fondo`."""
    return [pieza(k + 2, d, **EN_EL_CENTRO_DE_LA_VIRGEN) for k, d in enumerate(DOSIS)]


def _con_la_pieza(piezas, orden, **opciones):
    """`piezas` con la de ese `orden` medida de nuevo con `opciones` encima de `EN_EL_CENTRO_DE_LA_VIRGEN`."""
    nueva = pieza(orden, DOSIS[orden - 2], **{**EN_EL_CENTRO_DE_LA_VIRGEN, **opciones})
    return [nueva if q.orden == orden else q for q in piezas]


class TestLosAvisosConCadaFuenteDelCero:
    """CD3-REV1-02. CD3-D12: la referencia de los dos avisos es el CERO de la curva, en sus tres fuentes (la media de las piezas de 0 cGy, la virgen montada y la pieza de menor dosis); las pruebas de siempre
    solo usaban una pieza de 0 cGy de cero. Aqui las diez piezas estan en el centro de la virgen y ninguna avisa hasta que una se aparta."""

    def test_con_la_virgen_de_cero_nada_avisa_si_todo_coincide(self, virgen_con_fondo, en_el_centro):
        c = _cd().ajustar(en_el_centro, virgen=virgen_con_fondo)
        assert c.cero["fuente"] == "pelicula_virgen" and c.avisos == ()

    def test_con_la_virgen_de_cero_el_fondo_distinto_nombra_su_pieza_y_no_cambia_el_estado(self, virgen_con_fondo, en_el_centro):
        a = _cd().ajustar(en_el_centro, virgen=virgen_con_fondo)
        b = _cd().ajustar(_con_la_pieza(en_el_centro, 5, blanco=250.0), virgen=virgen_con_fondo)
        assert b.cero["fuente"] == "pelicula_virgen" and len(b.avisos) == 1 and b.avisos[0].startswith(EXPOSICION.format(orden=5, nominal=200)), b.avisos
        assert "el 0.00 % de su fondo está en el blanco máximo y el 100.00 % del fondo del cero" in b.avisos[0]
        assert {k: b.estado(k) for k in CAPAS} == {k: a.estado(k) for k in CAPAS}

    def test_con_la_virgen_de_cero_otro_lugar_del_vidrio_nombra_su_pieza_y_no_cambia_el_estado(self, virgen_con_fondo, en_el_centro):
        a = _cd().ajustar(en_el_centro, virgen=virgen_con_fondo)
        b = _cd().ajustar(_con_la_pieza(en_el_centro, 6, posicion_mm=(54.0, 24.0)), virgen=virgen_con_fondo)
        assert len(b.avisos) == 1 and b.avisos[0].startswith(OTRO_LUGAR.format(orden=6, nominal=300)) and "a 30.0 mm del centro del cero (más de 20 mm)" in b.avisos[0], b.avisos
        assert {k: b.estado(k) for k in CAPAS} == {k: a.estado(k) for k in CAPAS}

    def test_con_la_pieza_de_menor_dosis_de_cero_el_fondo_distinto_nombra_su_pieza_y_no_cambia_el_estado(self, en_el_centro):
        a = _cd().ajustar(en_el_centro)
        b = _cd().ajustar(_con_la_pieza(en_el_centro, 5, blanco=250.0))
        c = _cd().ajustar(_con_la_pieza(en_el_centro, 2, blanco=250.0))
        assert a.cero["fuente"] == "pieza_de_menor_dosis" and a.avisos == ()
        assert len(b.avisos) == 1 and b.avisos[0].startswith(EXPOSICION.format(orden=5, nominal=200)), b.avisos
        assert {k: b.estado(k) for k in CAPAS} == {k: a.estado(k) for k in CAPAS}
        assert len(c.avisos) == 9 and not any(x.startswith("pieza 2 (") for x in c.avisos), "si el fondo distinto es el del cero avisan las otras nueve, y el cero no avisa de si mismo"

    def test_con_la_pieza_de_menor_dosis_de_cero_otro_lugar_del_vidrio_nombra_su_pieza_y_no_cambia_el_estado(self, en_el_centro):
        a = _cd().ajustar(en_el_centro)
        b = _cd().ajustar(_con_la_pieza(en_el_centro, 6, posicion_mm=(54.0, 24.0)))
        assert len(b.avisos) == 1 and b.avisos[0].startswith(OTRO_LUGAR.format(orden=6, nominal=300)) and "a 30.0 mm del centro del cero (más de 20 mm)" in b.avisos[0], b.avisos
        assert {k: b.estado(k) for k in CAPAS} == {k: a.estado(k) for k in CAPAS}

    def test_con_varias_piezas_de_0_cgy_la_referencia_es_su_media(self):
        """Dos piezas de 0 cGy, una con todo el fondo en el blanco y en x = 0 mm y la otra sin fondo y en x = 60 mm: la referencia es su media (fondo 0.5, centro en x = 30 mm); la primera sola o la ultima daria
        avisos en las ocho piezas."""
        piezas = por_netod(DOSIS_DE_LA_SEPARACION, [0.0100 * (k + 1) for k in range(8)])
        piezas.append(a_mano(20, 0, 0.0, 200.0, 0.2, posicion={"x": 60.0, "y": 0.0}, fondo=0.0))
        piezas[0] = dataclasses.replace(piezas[0], posicion_mm={"x": 0.0, "y": 0.0}, fondo_blanco=1.0)
        for i in range(1, 9):
            piezas[i] = dataclasses.replace(piezas[i], posicion_mm={"x": 30.0, "y": 0.0}, fondo_blanco=0.5)
        assert _cd().ajustar(piezas).avisos == ()
        piezas[3] = dataclasses.replace(piezas[3], posicion_mm={"x": 60.0, "y": 0.0})
        c = _cd().ajustar(piezas)
        assert len(c.avisos) == 1 and c.avisos[0].startswith(OTRO_LUGAR.format(orden=4, nominal=150)) and "a 30.0 mm del centro del cero (más de 20 mm)" in c.avisos[0], c.avisos


class TestLaCopiaGuardadaYSuReajuste:
    """CD3-REV1-03. `ajustar(copia.piezas)` (CD.4, `recalcular`) rehace la curva desde lo guardado: lo que `curva_desde_dict` acepta tiene que poder reajustarse, y lo que no puede, se rechaza al leerlo."""

    def test_una_pieza_no_medible_vuelve_de_su_copia(self, grande):
        """El rechazo de una pieza «ok» sin su valor no toca a una «no medible», que no trae ningun numero (CD.2) y cuya cadena de captura es lo que alcanzo a leer (nada, si el archivo no se lee)."""
        c = _cd().ajustar(list(grande.piezas) + [_cd().pieza_de_calibracion(30, 700.0, 700.0, medir(b"basura"))])
        assert c.piezas[-1].estado.startswith("no medible: ") and c.piezas[-1].cadena == {"equipo": None, "bits": None, "dpi": None, "formato": None}
        d = json.loads(json.dumps(c.como_dict()))
        assert _cd().curva_desde_dict(d).como_dict() == d

    def test_una_cadena_distinta_pero_bien_tipada_se_nombra_al_reajustar(self, grande):
        d = json.loads(json.dumps(grande.como_dict()))
        d["piezas"][3]["cadena"]["dpi"] = 600.0
        c = _cd().ajustar(_cd().curva_desde_dict(d).piezas)
        for capa in CAPAS:
            assert c.estado(capa).startswith(OTRA_CADENA) and "TIFF" in c.estado(capa) and "600 ppp" in c.estado(capa) and "150 ppp" in c.estado(capa), c.estado(capa)

    def test_ajustar_rehace_lo_derivado_y_no_hereda_lo_guardado(self, grande):
        """Lo derivado de cada capa de una pieza (su netOD y la u de esta, la dosis contada desde el cero, el residuo y si esta en el rango) se rehace desde lo MEDIDO (valor, u y recorte): una copia con esos
        numeros cambiados a mano da la misma curva que la sana (barrido de hojas de la correccion: `logs/CD3/correccion_ronda1/barrido_de_hojas.py`)."""
        d = json.loads(json.dumps(grande.como_dict()))
        for q in d["piezas"]:
            for fila in q["capas"].values():
                fila.update(netod=123.0, u_netod=123.0, dosis_cgy=123.0, residuo_pct=123.0, en_el_rango=True)
        assert _cd().ajustar(_cd().curva_desde_dict(d).piezas).como_dict() == grande.como_dict()

    def test_una_pieza_irradiada_de_valor_0_con_su_netod_guardada_no_hace_lanzar_a_ajustar(self, grande):
        """Un escaneo negro (valor 0) no tiene logaritmo: su netOD queda en None, y la que traiga una copia inconsistente no se hereda (antes: `ZeroDivisionError` al medir su u relativa). La pieza de 0 cGy con
        valor 0 es otro caso (CD3-PROD-01, cerrado el 30-10 por CD3-PROD-D1: `TestElContenidoNoHaceLanzarAAjustar`) y no se prueba aqui."""
        d = json.loads(json.dumps(grande.como_dict()))
        d["piezas"][3]["capas"]["G"]["valor"] = 0.0
        c = _cd().ajustar(_cd().curva_desde_dict(d).piezas)
        assert c.piezas[3].capas["G"]["netod"] is None and c.piezas[3].capas["G"]["u_netod"] is None and c.piezas[3].capas["G"]["residuo_pct"] is None


class TestLaPiezaDelCeroSeNombraPorSuDosisNominal:
    """CD3-REV1-04. Todos los textos de la curva nombran una pieza por su dosis NOMINAL («la pieza de 350 cGy», «la pieza 6 (300 cGy)»); el estado «guia» nombraba la de menor dosis por su dosis MEDIDA, y una
    misma pieza salia con dos numeros. Ahora el estado la nombra por la nominal y el detalle del cero, cuando la medida es otra, dice cual fue (con ella se cuentan las demas dosis, CD3-M1)."""

    def _curva(self, medida):
        return _cd().ajustar([pieza(2, 50, medida=medida, lado_mm=GRANDE)] + [pieza(k + 3, d, lado_mm=GRANDE) for k, d in enumerate(DOSIS[1:])])

    def test_con_la_dosis_medida_distinta_de_la_nominal_el_estado_dice_la_nominal(self):
        c = self._curva(48.7)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and c.cero["dosis_cgy"] == 48.7, "la dosis con que se cuentan las demas sigue siendo la medida (CD3-M1)"
        assert c.estado("G") == GUIA.format(dosis=50) and not any("48.7" in c.estado(capa) for capa in CAPAS), {capa: c.estado(capa) for capa in CAPAS}

    def test_con_la_dosis_medida_distinta_de_la_nominal_el_detalle_dice_las_dos(self):
        assert self._curva(48.7).cero["detalle"] == "la pieza 2 (50 cGy, medida en 48.7 cGy, la de menor dosis): solo guía"

    def test_con_la_dosis_medida_igual_a_la_nominal_el_detalle_no_cambia(self):
        c = self._curva(50.0)
        assert c.cero["dosis_cgy"] == 50.0 and c.cero["detalle"] == "la pieza 2 (50 cGy, la de menor dosis): solo guía"
        assert c.estado("G") == GUIA.format(dosis=50)


# ===================================================================================================== (14) CD3-PROD-01 y CD3-PROD-02 (decision de Opus del 30-10, borradores/CD3/decision_PROD01_02.md)
# `ajustar` NUNCA lanza por el contenido: una medida sin valor positivo no sirve de cero (CD3-PROD-D1) y, en el modo guia, las replicas de la pieza que hace de cero y lo que no supera su dosis no entran
# al ajuste y se avisan (CD3-PROD-D2); una pieza que no entra al ajuste no trae residuo (CD3-PROD-D3). Los textos se ESCRIBEN aqui (no se importan, CD2-M1).
NO_SIRVE_DE_CERO = "la pieza {orden} ({nominal:g} cGy) no sirve de cero: su valor no es positivo en {capas} y sin un valor positivo no hay densidad óptica neta"
REPLICA_DEL_CERO = "es una réplica de la pieza que hace de cero (la pieza {orden})"
NO_SUPERA_AL_CERO = "su dosis medida ({medida:g} cGy) no supera la del cero ({cero:g} cGy)"
NETODS_DE_LA_SEPARACION = [0.0100 * (k + 1) for k in range(8)]


def _devic_g(orden, nominal, medida, desvio=0.0, valor=None):
    """Una pieza a mano con el valor de la respuesta de Devic del verde a su dosis MEDIDA (menos `desvio`), u relativa 0.0005; `valor` lo fija (0.0 = un escaneo negro)."""
    r = gen.RespuestaDevic(1100.0, 4600.0, 2.19)
    v = 200.0 * 10.0 ** (-r.netod(medida)) - desvio if valor is None else valor
    return a_mano(orden, nominal, medida, v, max(v, 1.0) * 0.0005)


class TestElContenidoNoHaceLanzarAAjustar:
    def test_una_pieza_de_0_cgy_de_valor_0_no_sirve_de_cero_y_ajustar_no_lanza(self):
        """CD3-PROD-01: un escaneo negro como la unica pieza de 0 cGy (CD.2 lo mide «ok» con valor 0) no sirve de cero: se avisa y sigue la regla del cero (aqui, la pieza de menor dosis, guia); la copia vuelve."""
        piezas = por_netod(DOSIS_DE_LA_SEPARACION, NETODS_DE_LA_SEPARACION)
        piezas[0] = a_mano(1, 0, 0.0, 0.0, 0.1)
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and c.cero["dosis_cgy"] == 50.0, c.cero
        assert NO_SIRVE_DE_CERO.format(orden=1, nominal=0, capas="R, G, B, gris") in c.avisos, c.avisos
        assert all(c.cero["capas"][k]["i0"] > 0 for k in CAPAS), c.cero["capas"]
        assert _cd().curva_desde_dict(json.loads(json.dumps(c.como_dict()))).como_dict() == c.como_dict()

    def test_una_pieza_de_0_cgy_de_valor_0_no_entra_en_la_media_de_las_que_sirven(self):
        """Con una pieza de 0 cGy buena (valor 200, u 0.2) y otra negra, el cero es solo la buena (no la media 100) y la negra se avisa."""
        piezas = por_netod(DOSIS_DE_LA_SEPARACION, NETODS_DE_LA_SEPARACION) + [a_mano(20, 0, 0.0, 0.0, 0.1)]
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "piezas_de_0_cgy" and c.cero["detalle"] == "las piezas de 0 cGy (pieza 1)", c.cero
        assert all(c.cero["capas"][k]["i0"] == 200.0 and c.cero["capas"][k]["u_i0"] == pytest.approx(0.2, rel=1e-12) for k in CAPAS), c.cero["capas"]
        assert NO_SIRVE_DE_CERO.format(orden=20, nominal=0, capas="R, G, B, gris") in c.avisos, c.avisos

    def test_una_pieza_de_0_cgy_de_valor_0_no_es_referencia_de_los_avisos(self):
        """CD3-D12: la referencia de los avisos es el cero de la curva; la pieza negra (en x = 100 mm) no es parte de el y no mueve el centro (las demas estan en x = 0)."""
        en = {"x": 0.0, "y": 0.0}
        piezas = [a_mano(1, 0, 0.0, 200.0, 0.2, posicion=en)]
        for k, (d, x) in enumerate(zip(DOSIS_DE_LA_SEPARACION, NETODS_DE_LA_SEPARACION)):
            valor = 200.0 * 10.0 ** (-x)
            piezas.append(a_mano(k + 2, d, d, valor, valor * 0.001, posicion=en))
        piezas.append(a_mano(20, 0, 0.0, 0.0, 0.1, posicion={"x": 100.0, "y": 0.0}))
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "piezas_de_0_cgy" and not any("otro lugar del vidrio" in a for a in c.avisos), c.avisos

    def test_la_pieza_negra_de_menor_dosis_no_hace_de_cero_guia(self):
        """Sin pieza de 0 cGy, la de menor dosis es un escaneo negro (valor 0): no sirve de cero; el cero es la siguiente (100 cGy) y la negra no entra porque su dosis no supera la del cero."""
        piezas = [_devic_g(1, 50, 50.0, valor=0.0)] + [_devic_g(k + 2, d, float(d)) for k, d in enumerate((100, 150, 200, 300, 400, 500, 600, 800))]
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and c.cero["dosis_cgy"] == 100.0 and all(c.cero["capas"][k]["i0"] > 0 for k in CAPAS), c.cero
        assert FUERA.format(orden=1, nominal=50, estado=NO_SUPERA_AL_CERO.format(medida=50, cero=100)) in c.avisos, c.avisos

    def test_las_replicas_de_la_pieza_que_hace_de_cero_no_entran_al_ajuste_y_se_avisan(self):
        """CD3-PROD-02: sin pieza de 0 cGy el cero es la de menor dosis; sus replicas (misma dosis nominal y medida) quedarian a 0 cGy del cero y el ajuste de los residuos relativos dividiria por 0."""
        piezas = [_devic_g(o, 50, 50.0, desvio) for o, desvio in ((1, 0.0), (2, 5.0), (3, 10.0))] + [_devic_g(k + 4, d, float(d)) for k, d in enumerate((100, 150, 200, 300, 400, 500, 600))]
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and c.cero["dosis_cgy"] == 50.0, c.cero
        for capa in CAPAS:
            assert c.capas[capa]["parametros"] is not None and c.capas[capa]["dosis_en_el_rango"] >= 1, (capa, c.estado(capa))
            assert not any(q.capas[capa]["en_el_rango"] for q in c.piezas if q.orden in (2, 3))
        for orden in (2, 3):
            assert FUERA.format(orden=orden, nominal=50, estado=REPLICA_DEL_CERO.format(orden=1)) in c.avisos, c.avisos

    def test_una_replica_del_cero_con_otra_dosis_medida_tampoco_entra_ni_trae_residuo(self):
        """Las replicas son las de la misma dosis NOMINAL (CD3-D5), midan lo que midan: la de 49.3 cGy junto a la de 48.7 que hace de cero quedaria a 0.6 cGy de el y no se distingue."""
        piezas = [_devic_g(1, 50, 48.7), _devic_g(2, 50, 49.3)] + [_devic_g(k + 3, d, float(d)) for k, d in enumerate((100, 150, 200, 300, 400, 500, 600))]
        c = _cd().ajustar(piezas)
        assert c.cero["dosis_cgy"] == 48.7 and FUERA.format(orden=2, nominal=50, estado=REPLICA_DEL_CERO.format(orden=1)) in c.avisos, (c.cero, c.avisos)
        replica = next(q for q in c.piezas if q.orden == 2)
        for capa in CAPAS:
            assert c.capas[capa]["dosis_en_el_rango"] >= 1, (capa, c.estado(capa))
            assert not replica.capas[capa]["en_el_rango"] and replica.capas[capa]["residuo_pct"] is None, (capa, replica.capas[capa])

    def test_una_pieza_de_otra_dosis_nominal_con_la_dosis_medida_del_cero_no_entra_y_se_avisa(self):
        """Dos dosis nominales (50 y 60) medidas las dos en 50 cGy: la de 60 queda a 0 cGy del cero y no entra (su dosis medida no supera la del cero)."""
        piezas = [_devic_g(1, 50, 50.0), _devic_g(2, 60, 50.0, 3.0)] + [_devic_g(k + 3, d, float(d)) for k, d in enumerate((100, 150, 200, 300, 400, 500, 600))]
        c = _cd().ajustar(piezas)
        assert FUERA.format(orden=2, nominal=60, estado=NO_SUPERA_AL_CERO.format(medida=50, cero=50)) in c.avisos, c.avisos
        assert all(c.capas[capa]["dosis_en_el_rango"] >= 1 for capa in CAPAS), {k: c.estado(k) for k in CAPAS}


# ===================================================================================================== (15) ampliacion del corrector sobre la decision de CD3-PROD-01/02 (30-10)
#
# Los mutantes extra del corrector (`scripts/cd3_decision_extra_mutantes.py` del anexo) sobre las lineas NUEVAS de la decision que PD1 a PD9 no tocan dejaban vivas seis guardas SIN prueba: el bucle que avisa lo
# que queda junto al cero en el modo guia (una pieza que no es «ok», una de 0 cGy con dosis medida, una irradiada sin dosis medida positiva: con None, el aviso reventaba con `TypeError`) y las piezas con valor 0
# solo en ALGUNAS capas (la ayuda las nombra a esas, en el orden de las capas, y los tres sitios que la usan piden las cuatro). Cada prueba fija una guarda; las mutaciones PE1 a PE7 la quitan.

def _con_capas_en_cero(pieza, *capas):
    """La misma pieza con el valor 0 SOLO en las capas dadas (un escaneo negro en una parte de las capas); el resto de las capas conserva su valor."""
    return dataclasses.replace(pieza, capas={c: ({**f, "valor": 0.0} if c in capas else f) for c, f in pieza.capas.items()})


class TestLasGuardasDeLaDecisionSobreElCero:
    @pytest.mark.parametrize("medida", [None, 0.0, -3.0])
    def test_en_modo_guia_una_pieza_sin_dosis_medida_positiva_no_hace_lanzar_ni_se_avisa_junto_al_cero(self, medida):
        """Sin pieza de 0 cGy ni virgen montada (modo guia, como las 21 piezas de H9), una irradiada sin dosis medida o con una que no es positiva queda «incompleta» por su fila, no hace lanzar a `ajustar`
        (con None, el aviso de lo que queda junto al cero formateaba None) y no recibe ademas el aviso de «no supera la dosis del cero»."""
        piezas = [_devic_g(1, 50, 50.0)] + [_devic_g(k + 2, d, float(d)) for k, d in enumerate((100, 150, 200, 300, 400, 500, 600))] + [a_mano(20, 800, medida, 100.0, 0.1)]
        c = _cd().ajustar(piezas)
        esperado = FALTA_DOSIS.format(orden=20, nominal=800) if medida is None else NO_POSITIVA.format(orden=20, nominal=800)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and all(c.estado(capa) == esperado for capa in CAPAS), {capa: c.estado(capa) for capa in CAPAS}
        assert not any(a.startswith("la pieza 20 ") for a in c.avisos), c.avisos
        assert _cd().curva_desde_dict(json.loads(json.dumps(c.como_dict()))).como_dict() == c.como_dict()

    def test_en_modo_guia_una_pieza_no_medible_se_avisa_una_sola_vez(self):
        """Solo las piezas «ok» pueden quedar junto al cero: una «no medible» de la misma dosis nominal y medida que la del cero ya se avisa por su estado, y no una segunda vez como replica."""
        no_medible = _cd().pieza_de_calibracion(30, 50.0, 50.0, medir(b"basura", "50.tif"))
        c = _cd().ajustar([_devic_g(1, 50, 50.0)] + [_devic_g(k + 2, d, float(d)) for k, d in enumerate((100, 150, 200, 300, 400, 500, 600))] + [no_medible])
        assert no_medible.estado.startswith("no medible: ")
        assert [a for a in c.avisos if a.startswith("la pieza 30 ")] == [FUERA.format(orden=30, nominal=50, estado=no_medible.estado)], c.avisos

    def test_en_modo_guia_una_pieza_de_0_cgy_con_dosis_medida_no_se_avisa_como_junto_al_cero(self):
        """Una pieza de 0 cGy que no sirve de cero se avisa por eso y no TAMBIEN como una irradiada que no supera la dosis del cero, aunque se le haya anotado una dosis medida."""
        piezas = [a_mano(1, 0, 3.0, 0.0, 0.1)] + [_devic_g(k + 2, d, float(d)) for k, d in enumerate((50, 100, 150, 200, 300, 400, 500, 600))]
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and c.cero["dosis_cgy"] == 50.0, c.cero
        assert [a for a in c.avisos if a.startswith("la pieza 1 ")] == [NO_SIRVE_DE_CERO.format(orden=1, nominal=0, capas="R, G, B, gris")], c.avisos

    @pytest.mark.parametrize("capas,texto", [(("G",), "G"), (("R", "gris"), "R, gris"), (("B", "R"), "R, B")])
    def test_la_pieza_de_0_cgy_con_valor_0_en_algunas_capas_no_sirve_y_el_aviso_nombra_solo_esas_en_el_orden_de_las_capas(self, capas, texto):
        """Basta una capa sin valor positivo para que la pieza no sirva de cero (netOD = log10(I0 / I) pide I0 > 0 en cada capa), y el aviso nombra EXACTAMENTE las que fallan, en el orden de `CAPAS_DEL_PISO`."""
        piezas = por_netod(DOSIS_DE_LA_SEPARACION, NETODS_DE_LA_SEPARACION)
        piezas[0] = _con_capas_en_cero(piezas[0], *capas)
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and all(c.cero["capas"][k]["i0"] > 0 for k in CAPAS), c.cero
        assert NO_SIRVE_DE_CERO.format(orden=1, nominal=0, capas=texto) in c.avisos, c.avisos

    def test_la_pieza_de_0_cgy_con_valor_0_en_una_capa_no_es_referencia_de_los_avisos(self):
        """CD3-D12 con una pieza de 0 cGy mala solo en el verde (en x = 100 mm): no es parte del cero y no mueve el centro de la referencia (las demas estan en x = 0)."""
        en = {"x": 0.0, "y": 0.0}
        piezas = [a_mano(1, 0, 0.0, 200.0, 0.2, posicion=en)]
        for k, (d, x) in enumerate(zip(DOSIS_DE_LA_SEPARACION, NETODS_DE_LA_SEPARACION)):
            valor = 200.0 * 10.0 ** (-x)
            piezas.append(a_mano(k + 2, d, d, valor, valor * 0.001, posicion=en))
        piezas.append(_con_capas_en_cero(a_mano(20, 0, 0.0, 200.0, 0.2, posicion={"x": 100.0, "y": 0.0}), "G"))
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "piezas_de_0_cgy" and c.cero["detalle"] == "las piezas de 0 cGy (pieza 1)", c.cero
        assert not any("otro lugar del vidrio" in a for a in c.avisos), c.avisos

    def test_la_pieza_de_menor_dosis_con_valor_0_en_una_capa_no_hace_de_cero_guia(self):
        """Como la prueba de la pieza negra de menor dosis, con un escaneo negro solo en el verde: no se escoge de cero (su I0 en el verde seria 0), el cero es la siguiente y la de menor dosis se avisa."""
        piezas = [_con_capas_en_cero(_devic_g(1, 50, 50.0), "G")] + [_devic_g(k + 2, d, float(d)) for k, d in enumerate((100, 150, 200, 300, 400, 500, 600, 800))]
        c = _cd().ajustar(piezas)
        assert c.cero["fuente"] == "pieza_de_menor_dosis" and c.cero["dosis_cgy"] == 100.0 and all(c.cero["capas"][k]["i0"] > 0 for k in CAPAS), c.cero
        assert FUERA.format(orden=1, nominal=50, estado=NO_SUPERA_AL_CERO.format(medida=50, cero=100)) in c.avisos, c.avisos
