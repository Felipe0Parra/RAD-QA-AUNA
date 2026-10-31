"""CD.6 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-92): LA BASE «DOSIS» EN EL MOTOR MENSUAL, la regla por capa, la regla del boton «Ver en dosis» y la curva efectiva.

CAUSA: el motor media en netOD o en valor de pixel y ni `analizar` ni nada del motor recibia una curva. H4: el borde a la mitad de la DOSIS no es el borde a la mitad de la netOD (en una pelicula que se satura
el 50 % de la dosis esta por encima del 50 % de la netOD).

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale del codigo bajo prueba (los generadores independientes de PF.0 y de CD.3, una curva LINEAL construida a mano y la imagen convertida pixel a pixel):
  (a) SIN CURVA, COMO ANTES: con las bases de siempre el resultado no lleva ninguna clave nueva, el parametro 42 no entra en sus parametros si el registro no lo trae, y una curva o una cadena con otra base
      es un error (no se ignora un argumento). Que TODO sea identico a la base bit a bit lo demuestra la compuerta del anexo (`cd6_diferencial.py`: las diez peliculas reales en los tres modos del piso).
  (b) LA CURVA LINEAL (D = k x, construida a mano, b = 0 y n = 1): el FWHM en dosis es el de netOD a 1e-9 mm en las cuatro capas; con una curva de Devic, no (el control: solo la curvatura mueve el borde).
  (c) LA VERDAD: una placa sintetica con la respuesta definida en netOD (la variante del generador de PF.0) y una curva hecha con piezas de la MISMA respuesta (el generador de CD.3): el FWHM en dosis de
      cada capa da los 100.000 x 99.000 mm de la placa a 0.05 mm, y los desfases los de su verdad; el de netOD sale mas ancho (+1.0 a +1.6 mm, mas cuanto mas se satura la capa); la dosis de la meseta es la
      de la placa (300 cGy) a 1 %.
  (d) CADA MOTIVO de `base_de_la_capa` se reproduce con su texto exacto.
  (e) LA BANDA EN DOSIS es la de la imagen convertida pixel a pixel: sus valores llevan EXACTAMENTE la media de la dosis de cada pixel, y los bordes quedan a 0.01 mm de los de la imagen convertida medida
      en valor de pixel, en las 8 peliculas del oraculo de OD.1 (las que esten; HI-0).
  (f-bis) LA REGLA DEL BOTON: cada una de las cinco condiciones de DC8, rota por separado, apaga `se_puede_pasar_a_dosis` con su motivo; con las cinco, encendida; mira la capa que se le pide.
      `curva_efectiva` elige la valida mas reciente de la cadena de la pelicula, ninguna si la unica valida es de otra cadena, y su motivo dice la regla entera.
  (g) EL ROJO RECORTADO sigue «no medible» en dosis, y el boton lo dice.
  Y la estructura: toda llamada de produccion a `perfil_central` y a `medir_perfil` pasa `curva=`; el parametro 42 tiene nombre, unidad y motivo; el aviso de la pelicula virgen; la cadena de la pelicula es la
  de CD.2; sin simbolos (DA-18).

  RONDA 1 DE LA REVISION (31-10, CD6-REV-*; cada una con la mutacion de `cd6_mutaciones.py` que la hace caer, Y01 en adelante): el aviso de la virgen es por la diferencia ABSOLUTA y solo existe si el piso del
      analisis ES el de una pelicula virgen (P1, PRU-01); `curva_efectiva` pide AL MENOS una capa valida (PRU-02); la condicion 4 del boton se juzga con la meseta mas oscura de los dos perfiles (PRU-03); la dosis de
      la meseta y su U salen de los dos perfiles (PRU-04); el ORDEN de la regla por capa y del boton, con varias condiciones rotas a la vez (PRU-05); y la placa de PF.0 del generador es la de HEAD, por su digest (PRU-06).

Rojo contra la base (el arbol de CD.5): el motor no tiene `BASE_DOSIS`, `cadena_de_la_pelicula` ni las reglas: las pruebas caen con su error (la variante del generador SI esta: va con la prueba).
Las pruebas importan la produccion POR PRUEBA. Lo caro (la placa de 600 ppp a 16 bits, unos 20 s, y sus analisis) es una fixture de modulo.
"""
import ast
import copy
import dataclasses
import gc
import hashlib
import importlib
import math
import os
import types
from pathlib import Path

import numpy as np
import pytest

import _corpus
import _piezas_de_calibracion_sinteticas as gp
import _placa_mensual_sintetica as gen

RAIZ = Path(__file__).resolve().parent.parent
TAM = 25.4 / 600.0
BASE_OD = "densidad óptica neta"                 # escritas AQUI a proposito: la prueba fija los textos, no los importa
BASE_VP = "valor de píxel normalizado"
BASE_DOSIS = "dosis"
VP_MINIMO = 0.5
EJES = ("crossplane", "inplane")
TODAS = ("R", "G", "B", "gris")
SIMBOLOS = "✓✗✔✘⚠❌✅❎☑☒"
FECHA = "2026-10-31"
DOSIS_MESETA = 300.0
RESP = {"R": gp.RespuestaDevic(700.0, 3300.0, 2.06), "G": gp.RespuestaDevic(1100.0, 4600.0, 2.19), "B": gp.RespuestaDevic(1750.0, 8200.0, 1.58)}       # las de CD.3 (del orden de H9)
DOSIS = (0, 50, 100, 150, 200, 300, 400, 500, 600)
V = dict(zip(("B", "G", "R"), gen.CALIB["virgen_bgr"]))           # la pelicula virgen de la placa: el I0 de las piezas es el MISMO
PISO_DE_LA_PLACA = {"R": V["R"], "G": V["G"], "B": V["B"], "gris": 0.299 * V["R"] + 0.587 * V["G"] + 0.114 * V["B"]}
NOMBRE = {"R": "roja", "G": "verde", "B": "azul", "gris": "gris"}
CLICS = {          # los de OD.1 (tests/test_od1_densidad_optica.py), copiados: las 8 peliculas de su oraculo
    "ML0": ((196, 143), (2542, 147), (2526, 2501), (171, 2480), (1371, 1330)),
    "EPSON007": ((207, 173), (2516, 153), (2553, 2507), (232, 2525), (1376, 1345)),
    "EPSON008_TIF": ((206, 189), (2517, 169), (2553, 2525), (230, 2542), (1376, 1362)),
    "EPSON030": ((166, 174), (2475, 158), (2507, 2512), (187, 2526), (1333, 1348)),
    "EPSON001_JPG": ((178, 255), (2541, 252), (2553, 2593), (203, 2608), (1368, 1435)),
    "EPSON001_TIF": ((178, 255), (2541, 252), (2553, 2593), (203, 2608), (1368, 1435)),
    "EPSON028": ((111, 200), (2452, 175), (2496, 2520), (124, 2525), (1287, 1362)),
    "EPSON029": ((215, 151), (2526, 195), (2494, 2542), (183, 2498), (1361, 1350)),
}

# Los textos de la regla, escritos aqui (si cambian, la prueba lo dice).
SIN_CURVA = "no hay curva de dosis"
PREFIJO = "no medible en dosis: "
GUIA = "la curva de la capa {nombre} es una guía: el cero es la pieza de {dosis:g} cGy"
NO_VALIDA = "la curva de la capa {nombre} no es válida: {estado}"
CERO_GUIA = "la curva de la capa {nombre} es una guía: su cero no es una pieza de 0 cGy ni la película virgen montada ({detalle})"
PISO_NO_VIRGEN = "el piso no es el de la película virgen ({origen}): la dosis lo exige"
SIN_CADENA = "no se conoce la cadena de captura de la película"
OTRA_CADENA = "la película se escaneó con otra cadena de captura que la calibración: {pelicula} contra {curva}"
RANGO = "la meseta (netOD {x:.3f}) pasa el rango útil de la curva de la capa {nombre} (hasta netOD {maxima:.3f}, {rango:g} cGy): no se extrapola"
NO_MEDIDA = "la capa {nombre} no se midió en densidad óptica neta, así que tampoco en dosis: {estado}"
REGLA = "la curva de un análisis es la de la calibración vigente más reciente con al menos una capa «válida» escaneada con la misma cadena de captura que la película"

# La placa de PF.0 que daba el generador de HEAD (el de antes de CD.6): el digest (sha256 de dtype, forma y bytes) de cada caso, medido con `git show HEAD:tests/_placa_mensual_sintetica.py`
# (anexo: logs/CD6/correccion_ronda1/golden_pf0.py, que tambien lo mide con el generador del arbol y exige que den lo mismo). Un cambio al camino SIN la variante en netOD (la respuesta de PF.0, el ruido,
# el giro, la tinta, las extensiones, el redondeo) mueve el digest. Si algun dia se cambia A PROPOSITO la placa de PF.0, se cambia aqui con su motivo.
PLACAS_DE_PF0 = {
    "ruido_8bits": (dict(dpi=50, seed=3), "0c81bef09d8bc1837e0bbf0ea032478e8d001d3116f11bc13d782b85890244e2"),
    "16bits_sin_ruido_giro": (dict(dpi=50, seed=1, bits=16, variante="A", theta_deg=0.4, ruido=0.0), "e4f090e4eb6cb109812cb232d09b1f449adbec34ee0ee25d43b841bfabd51c4a"),
    "con_alfa_giro_y_extensiones": (dict(dpi=50, seed=2, bits=8, alfa=True, variante="B", theta_deg=-0.7, ruido=0.0, beta=0.02, cupula_pct_40mm=-3.5),
                                    "e6a40a0c6bd725ffe4abd6530a03d1a9d147da44f30ed9c90a215c7136713cd9"),
}


def digest_del_arreglo(a):
    return hashlib.sha256(f"{a.dtype}|{a.shape}|".encode() + a.tobytes()).hexdigest()


def _pm():
    """El motor, importado POR PRUEBA (en la base no tiene la dosis y cada prueba cae con su error)."""
    return importlib.import_module("analisisImagenes.placa_mensual")


def _pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _cd():
    return importlib.import_module("analisisImagenes.curva_dosis")


def _P(base=BASE_OD, **cambios):
    P = copy.deepcopy(_pm().VALORES_DE_LA_GEOMETRIA)
    P["base_de_la_medida"] = base
    P.update(cambios)
    return P


def referencia(bits, valores=None):
    """Una `ReferenciaVirgen` valida cuyo valor por capa es EXACTAMENTE el pedido (por omision, la virgen de la placa), como la de OD.1."""
    pel = _pel()
    valores = PISO_DE_LA_PLACA if valores is None else valores
    capas = {c: pel.CapaDelPiso(c, "ok", valores[c], 1000, 1.0, None, None, valores[c]) for c in TODAS}
    procedencia = {"archivo": "virgen.tif", "sha256": "ab" * 32, "bytes": 1, "formato": "TIFF", "bits": bits, "dpi_declarado": 600.0, "clase_resolucion": "coincide", "forma": [10, 10],
                   "fecha_escaneo": None, "equipo": None, "calidad_jpeg": None, "submuestreo": None, "orientacion_declarada": None, "fecha_calculo": FECHA, "version": pel.VERSION_PISO_VIRGEN}
    return pel.ReferenciaVirgen("ok", capas, (), (), {"caja": [0, 0, 1, 1], "n": 1000, "area_mm2": 1.0}, procedencia, {})


def calibrar(respuestas=RESP, dosis=DOSIS, bits=16, cero=True):
    """La curva (CD.3) de piezas sinteticas de 5 x 5 cm de la MISMA respuesta y el MISMO I0 que la placa, sin ruido, a 600 ppp y en TIFF (la cadena de la placa). Sin `cero`, la de menor dosis lo hace."""
    piezas = []
    for k, d in enumerate(dosis):
        if d == 0 and not cero:
            continue
        datos = gp.pieza_de_dosis(d, (respuestas["R"], respuestas["G"], respuestas["B"]), i0=(V["R"], V["G"], V["B"]), sigma=0.0, bits=bits, dpi=600.0, lado_mm=50.0, semilla=k + 1).datos
        medida = _pel().medir_pieza_uniforme(datos, _P(), f"{d}.tif", FECHA, escala="declarada")
        piezas.append(_cd().pieza_de_calibracion(k + 1, float(d), float(d), medida))
    return _cd().ajustar(piezas)


def con_capa(curva, capa, **cambios):
    """La curva con la capa `capa` cambiada (para romper UNA condicion; la curva es inmutable: es otra)."""
    capas = copy.deepcopy(curva.capas)
    capas[capa].update(cambios)
    return dataclasses.replace(curva, capas=capas)


def lineal(curva, k=1000.0):
    """La curva con D = k x EXACTA en las cuatro capas (b = 0, n = 1), con un rango que cubre cualquier meseta."""
    capas = {c: {**copy.deepcopy(curva.capas[c]), "parametros": {"a": k, "b": 0.0, "n": 1.0}, "netod_maxima": 5.0, "rango_cgy": 5000.0} for c in TODAS}
    return dataclasses.replace(curva, capas=capas)


def ancha(curva):
    """La curva con un rango que cubre cualquier meseta (para medir la banda de peliculas reales con una curva de otra cadena)."""
    capas = {c: {**copy.deepcopy(curva.capas[c]), "netod_maxima": 5.0, "rango_cgy": 50000.0} for c in TODAS}
    return dataclasses.replace(curva, capas=capas)


def texto_de_la_cadena(c):
    equipo = c["equipo"] or "escáner sin declarar"
    dpi = "sin resolución" if c["dpi"] is None else f"{c['dpi']:g} ppp"
    return f"{equipo}, {c['bits']} bits, {dpi}, {c['formato']}"


def nivel_de_netod(perfil, netod):
    """El nivel de meseta cuya netOD contra el piso del perfil `perfil` es `netod` (netOD = log10(piso / meseta))."""
    return perfil.piso / 10.0 ** netod


def con_mesetas(resultado, capa, **netods):
    """El resultado con la meseta de los perfiles dados de la capa `capa` puesta en la netOD pedida (`crossplane=`, `inplane=`). Lo que depende de que los DOS perfiles midan cosas distintas no se puede probar con
    la placa de la escena, donde dan la misma meseta a 1e-9 (CD6-REV-PRU-03 y -04)."""
    medida = resultado.capas[capa]
    cambios = {eje: dataclasses.replace(getattr(medida, eje), meseta=nivel_de_netod(getattr(medida, eje), netod)) for eje, netod in netods.items()}
    return dataclasses.replace(resultado, capas={**resultado.capas, capa: dataclasses.replace(medida, **cambios)})


@pytest.fixture(scope="module")
def escena():
    """La placa de la verdad (variante en netOD, 16 bits, 600 ppp, sin ruido), su curva, su virgen y sus dos analisis (netOD y dosis)."""
    pm, pel = _pm(), _pel()
    placa = gen.generar("tiff", bits=16, variante="A", theta_deg=0.4, seed=1, ruido=0.0, respuestas_netod=RESP, dosis_meseta_cgy=DOSIS_MESETA)
    pelicula = pel.leer_pelicula(placa.datos)
    puntos = [placa.verdad.marcas_px[k] for k in ("UL", "UR", "DR", "DL", "C")]
    cadena = pm.cadena_de_la_pelicula(placa.datos, pelicula)
    curva = calibrar()
    ref = referencia(16)
    od = pm.analizar(pelicula, puntos, _P(), modo_piso="virgen", referencia_virgen=ref)
    do = pm.analizar(pelicula, puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=ref, curva=curva, cadena=cadena)
    yield types.SimpleNamespace(placa=placa, verdad=placa.verdad, pelicula=pelicula, puntos=puntos, cadena=cadena, curva=curva, ref=ref, od=od, do=do)
    gc.collect()


def efectiva_de(curva):
    return _pm().CurvaEfectiva(curva, 7, "L-31", "2026-10-30")


# ===================================================================================================== (a) sin curva, como antes

class TestSinCurvaComoAntes:
    def test_un_analisis_en_netod_no_lleva_ninguna_clave_nueva(self, escena):
        d = escena.od.como_dict()
        assert escena.od.base == BASE_OD and escena.od.curva is None and escena.od.cadena is None and escena.od.avisos_de_la_dosis == ()
        assert not {"curva", "cadena", "avisos_de_la_dosis"} & set(d)
        for c in TODAS:
            assert escena.od.capas[c].base is None and escena.od.capas[c].motivo_de_la_base is None and escena.od.capas[c].dosis_meseta_cgy is None
            assert not {"base", "motivo_de_la_base", "dosis_meseta_cgy", "u_dosis_meseta_cgy"} & set(d["capas"][c])

    def test_el_parametro_42_no_entra_en_un_registro_que_no_lo_trae(self, escena):
        """Un registro guardado antes de CD.6 (41 parametros) se mide en netOD con sus 41: el resultado no gana el parametro 42 (lo que se guardo es lo que se mide)."""
        P = _P()
        del P["diferencia_virgen_maxima_pct"]
        r = _pm().analizar(escena.pelicula, escena.puntos, P, modo_piso="virgen", referencia_virgen=escena.ref)
        assert "diferencia_virgen_maxima_pct" not in r.parametros and len(r.parametros) == 41
        assert r.como_dict()["capas"] == escena.od.como_dict()["capas"], "el parametro 42 no cambia ninguna medida en netOD"

    @pytest.mark.parametrize("base", [BASE_OD, BASE_VP])
    def test_una_curva_o_una_cadena_con_otra_base_es_un_error(self, escena, base):
        pm = _pm()
        with pytest.raises(ValueError, match="solo se usan con la base «dosis»"):
            pm.analizar(escena.pelicula, escena.puntos, _P(base), modo_piso="virgen", referencia_virgen=escena.ref, curva=escena.curva)
        with pytest.raises(ValueError, match="solo se usan con la base «dosis»"):
            pm.analizar(escena.pelicula, escena.puntos, _P(base), modo_piso="virgen", referencia_virgen=escena.ref, cadena=escena.cadena)

    def test_las_funciones_de_la_base_piden_la_curva_solo_en_dosis(self):
        pm = _pm()
        with pytest.raises(ValueError, match="necesita la curva de dosis de la capa"):
            pm.normalizar(BASE_DOSIS, [100.0], 170.0, 50.0)
        with pytest.raises(ValueError, match="solo se usa con la base «dosis»"):
            pm.valores_en_la_base(BASE_OD, [100.0], 170.0, curva=object())
        with pytest.raises(ValueError, match="no está implementada"):
            pm.normalizar("dosis absoluta", [100.0], 170.0, 50.0)
        assert pm.BASE_DOSIS == BASE_DOSIS and pm.BASES == (BASE_OD, BASE_VP, BASE_DOSIS) and pm.BASE_POR_OMISION == BASE_OD, "la dosis nunca es la base por omision"

    def test_una_curva_que_no_es_una_curva_es_un_error(self, escena):
        with pytest.raises(ValueError, match="es una `CurvaDeDosis`"):
            _pm().analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=escena.ref, curva=escena.curva.como_dict(), cadena=escena.cadena)


# ===================================================================================================== (b) la curva lineal

class TestLaCurvaLinealEsElControl:
    def test_con_una_curva_lineal_y_sin_suavizado_el_fwhm_en_dosis_es_el_de_netod(self, escena):
        """Sin suavizado (`suavizado_perfil_mm` = 0) la unica diferencia entre las dos bases es la curva: con D = k x, la misma medida a 1e-9 mm (en la placa plana y sin ruido, donde la meseta en
        dosis, la dosis media, y la de netOD, el nivel medio, son el mismo nivel)."""
        pm = _pm()
        od = pm.analizar(escena.pelicula, escena.puntos, _P(suavizado_perfil_mm=0.0), modo_piso="virgen", referencia_virgen=escena.ref)
        do = pm.analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS, suavizado_perfil_mm=0.0), modo_piso="virgen", referencia_virgen=escena.ref, curva=lineal(escena.curva), cadena=escena.cadena)
        for c in TODAS:
            for eje in EJES:
                a, b = getattr(od.capas[c], eje), getattr(do.capas[c], eje)
                assert a.ok and b.ok, (c, eje, a.estado, b.estado)
                assert b.fwhm_mm == pytest.approx(a.fwhm_mm, abs=1e-9), (c, eje)
                for x, y in zip(a.bordes_rad_px, b.bordes_rad_px):
                    assert y == pytest.approx(x, abs=1e-7), (c, eje)

    def test_con_el_suavizado_de_siempre_la_diferencia_es_solo_la_del_suavizado(self, escena):
        """CD6-D3: en dosis se suaviza la dosis (la imagen convertida) y en netOD el nivel (OD.1): con D = k x quedan a 0.005 mm (medido el 31-10: 0.0014 mm en el rojo, la capa mas saturada)."""
        do = _pm().analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=escena.ref, curva=lineal(escena.curva), cadena=escena.cadena)
        for c in TODAS:
            for eje in EJES:
                assert getattr(do.capas[c], eje).fwhm_mm == pytest.approx(getattr(escena.od.capas[c], eje).fwhm_mm, abs=0.005), (c, eje)

    def test_con_la_curva_de_devic_no_lo_es(self, escena):
        for c in TODAS:
            for eje in EJES:
                assert getattr(escena.od.capas[c], eje).fwhm_mm - getattr(escena.do.capas[c], eje).fwhm_mm > 0.9, (c, eje)


# ===================================================================================================== (c) la verdad

class TestLaVerdadEnDosis:
    def test_la_curva_de_la_escena_es_valida_y_cubre_la_meseta(self, escena):
        for c in TODAS:
            assert escena.curva.estado(c) == "válida" and escena.curva.rango(c) == 600.0, (c, escena.curva.estado(c))
        assert escena.curva.cero["fuente"] == "piezas_de_0_cgy" and escena.curva.cadena == escena.cadena

    @pytest.mark.parametrize("capa", TODAS)
    def test_el_fwhm_en_dosis_es_el_de_la_placa(self, escena, capa):
        m = escena.do.capas[capa]
        assert escena.do.base == BASE_DOSIS and m.ok and m.base == BASE_DOSIS and m.motivo_de_la_base is None, (capa, m.estado)
        assert escena.verdad.FWHM_x == pytest.approx(100.0, abs=1e-6) and escena.verdad.FWHM_y == pytest.approx(99.0, abs=1e-6)
        assert m.crossplane.fwhm_mm == pytest.approx(100.0, abs=0.05), capa
        assert m.inplane.fwhm_mm == pytest.approx(99.0, abs=0.05), capa

    @pytest.mark.parametrize("capa", TODAS)
    def test_los_desfases_en_dosis_son_los_de_la_placa(self, escena, capa):
        exceso = escena.verdad.exceso
        lados = {"izquierdo": "L", "derecho": "R", "superior": "T", "inferior": "B"}
        for lado, clave in lados.items():
            assert escena.do.capas[capa].coincidencia_mm[lado] == pytest.approx(exceso[clave], abs=0.05), (capa, lado)

    def test_en_netod_sale_mas_ancho_cuanto_mas_se_satura_la_capa(self, escena):
        anchos = {c: escena.od.capas[c].crossplane.fwhm_mm for c in ("R", "G", "B")}
        for c, ancho in anchos.items():
            assert ancho - 100.0 > 0.9, (c, ancho)
        assert anchos["R"] > anchos["G"] > anchos["B"], anchos

    @pytest.mark.parametrize("capa", TODAS)
    def test_la_dosis_de_la_meseta_es_la_de_la_placa_con_su_u(self, escena, capa):
        m = escena.do.capas[capa]
        assert m.dosis_meseta_cgy == pytest.approx(DOSIS_MESETA, rel=0.01), capa
        assert m.u_dosis_meseta_cgy is not None and 0.0 < m.u_dosis_meseta_cgy < 0.05 * DOSIS_MESETA, (capa, m.u_dosis_meseta_cgy)
        d = escena.do.como_dict()["capas"][capa]
        assert d["base"] == BASE_DOSIS and d["dosis_meseta_cgy"] == m.dosis_meseta_cgy and d["u_dosis_meseta_cgy"] == m.u_dosis_meseta_cgy

    def test_la_u_de_la_meseta_es_la_de_la_curva_con_la_dispersion_de_la_meseta(self, escena):
        """DC10 (CD6-D7): U = incertidumbre de la curva en la netOD de la dosis de la meseta, con la u de la pelicula = la dispersion relativa de las dos mesetas / ln 10. La dosis esperada se calcula AQUI, de la
        curva y de las dos mesetas (CD6-REV-PRU-04: antes salia del `dosis_meseta_cgy` del propio motor y daba igual con cualquier dosis)."""
        m = escena.do.capas["G"]
        dosis = float(np.mean([escena.curva.dosis("G", math.log10(getattr(m, e).piso / getattr(m, e).meseta)) for e in EJES]))
        rel = math.sqrt(np.mean([(getattr(m, e).desviacion_meseta / getattr(m, e).meseta) ** 2 for e in EJES]))
        esperada = escena.curva.incertidumbre("G", escena.curva.netod("G", dosis), rel / math.log(10.0))
        assert m.dosis_meseta_cgy == pytest.approx(dosis, rel=1e-12)
        assert m.u_dosis_meseta_cgy == pytest.approx(esperada, rel=1e-12)

    def test_la_dosis_y_su_u_con_los_dos_perfiles_distintos(self, escena):
        """CD6-D7 (CD6-REV-PRU-04), con los dos perfiles de UNA capa midiendo cosas distintas (en la placa de la escena coinciden a 1e-9, y tomar un solo eje daba lo mismo): la dosis de la meseta es la MEDIA de las
        de sus dos mesetas, y su U la de la curva en la netOD de esa dosis con la u de la pelicula = la raiz de la media de los cuadrados de las dos dispersiones relativas / ln 10 (no la de un perfil, ni la media
        simple). Las esperadas salen de la curva (CD.3) y de las mesetas, no del motor. `_dosis_de_la_meseta` es la funcion que implementa esa decision y la unica a la que se le pueden dar dos perfiles distintos."""
        pm = _pm()
        m = escena.do.capas["G"]
        piso = m.crossplane.piso
        x = {"crossplane": 0.15, "inplane": 0.21}                       # la netOD de cada meseta
        dispersion = {"crossplane": 0.4, "inplane": 1.6}                # la dispersion de sus muestras (niveles)
        perfiles = {e: dataclasses.replace(getattr(m, e), meseta=nivel_de_netod(getattr(m, e), x[e]), desviacion_meseta=dispersion[e]) for e in EJES}
        dosis, u = pm._dosis_de_la_meseta(pm.curva_de_la_capa(escena.curva, "G"), piso, perfiles)
        dosis_de = {e: escena.curva.dosis("G", x[e]) for e in EJES}
        esperada = float(np.mean(list(dosis_de.values())))
        relativas = [dispersion[e] / perfiles[e].meseta for e in EJES]
        relativa = math.sqrt(np.mean([r ** 2 for r in relativas]))
        assert dosis == pytest.approx(esperada, rel=1e-9)
        assert u == pytest.approx(escena.curva.incertidumbre("G", escena.curva.netod("G", esperada), relativa / math.log(10.0)), rel=1e-9)
        assert min(abs(esperada - d) for d in dosis_de.values()) > 5.0, "la media no es la de ninguno de los dos perfiles (la prueba discrimina)"
        for otra in (relativas[0], relativas[1], float(np.mean(relativas))):
            assert abs(relativa - otra) > 0.001, "la raiz de la media de los cuadrados no es la de un perfil ni la media simple (la prueba discrimina)"
        sin_dispersion = dict(perfiles, inplane=dataclasses.replace(perfiles["inplane"], desviacion_meseta=None))
        assert pm._dosis_de_la_meseta(pm.curva_de_la_capa(escena.curva, "G"), piso, sin_dispersion) == (None, None), "sin la dispersion de un perfil no hay dosis de la meseta"

    @pytest.mark.parametrize("capa", TODAS)
    def test_los_niveles_de_la_altura_media_y_la_penumbra_son_los_de_la_dosis(self, escena, capa):
        """Los niveles que se dibujan (`altura_media`, `nivel_penumbra_alta` y `_baja`) tienen el 50, el 80 y el 20 % de la DOSIS de la meseta (la inversa de la curva, `nivel_de_la_base`)."""
        pm = _pm()
        cc = pm.curva_de_la_capa(escena.curva, capa)
        for eje in EJES:
            m = getattr(escena.do.capas[capa], eje)
            meseta = float(pm.valores_en_la_base(BASE_DOSIS, m.meseta, m.piso, cc))
            for nivel, fraccion in ((m.altura_media, 0.5), (m.nivel_penumbra_alta, 0.8), (m.nivel_penumbra_baja, 0.2)):
                assert float(pm.valores_en_la_base(BASE_DOSIS, nivel, m.piso, cc)) == pytest.approx(fraccion * meseta, rel=1e-9), (capa, eje, fraccion)
            assert m.altura_media != pytest.approx(pm.nivel_de_la_base(BASE_OD, 0.5, m.piso, m.meseta), rel=1e-6), "el 50 % de la dosis no es el de la netOD"

    def test_el_resultado_en_dosis_dice_su_curva_y_su_cadena(self, escena):
        d = escena.do.como_dict()
        assert escena.do.curva is escena.curva and d["curva"] == escena.curva.como_dict() and d["cadena"] == escena.cadena and d["avisos_de_la_dosis"] == []
        assert d["parametros"]["base_de_la_medida"] == BASE_DOSIS and d["parametros"]["diferencia_virgen_maxima_pct"] == 2.0

    def test_el_barrido_en_dosis_mide_en_dosis(self, escena):
        b = _pm().barrido(escena.do)
        assert b.ok
        for c in TODAS:
            central = b.ejes["crossplane"].capas[c].central
            assert central.fwhm_mm == escena.do.capas[c].crossplane.fwhm_mm, c
            assert b.ejes["crossplane"].capas[c].estadistica.media_mm == pytest.approx(100.0, abs=0.05), c


# ===================================================================================================== (d) cada motivo de base_de_la_capa

class TestCadaMotivoDeLaRegla:
    def test_con_todo_en_orden_es_dosis(self, escena):
        for c in TODAS:
            assert _pm().base_de_la_capa(escena.curva, c, escena.od.piso, escena.cadena) == (BASE_DOSIS, None)

    def test_sin_curva(self, escena):
        assert _pm().base_de_la_capa(None, "G", escena.od.piso, escena.cadena) == (BASE_OD, SIN_CURVA)

    def test_una_curva_guia(self, escena):
        guia = calibrar(cero=False)
        assert guia.cero["fuente"] == "pieza_de_menor_dosis"
        assert _pm().base_de_la_capa(guia, "G", escena.od.piso, escena.cadena) == (BASE_OD, GUIA.format(nombre="verde", dosis=50))

    def test_una_capa_no_valida(self, escena):
        mala = con_capa(escena.curva, "R", estado="no válida: el residuo de la pieza de 50 cGy es +4.00 % (la tolerancia es ±5 %)")
        assert _pm().base_de_la_capa(mala, "R", escena.od.piso, escena.cadena) == (BASE_OD, NO_VALIDA.format(nombre="roja", estado=mala.estado("R")))
        assert _pm().base_de_la_capa(mala, "G", escena.od.piso, escena.cadena) == (BASE_DOSIS, None), "la regla mira la curva de SU capa"

    def test_una_curva_incompleta(self, escena):
        corta = calibrar(dosis=(0, 50, 100, 150))
        estado = corta.estado("B")
        assert estado.startswith("incompleta: ")
        assert _pm().base_de_la_capa(corta, "B", escena.od.piso, escena.cadena) == (BASE_OD, NO_VALIDA.format(nombre="azul", estado=estado))

    def test_un_cero_que_no_es_de_0_cgy_aunque_la_capa_diga_valida(self, escena):
        """La condicion 5 se juzga por la FUENTE del cero, no solo por el estado (una copia guardada cuyo estado diga «valida» con el cero de la pieza de menor dosis sigue sin pasar a dosis)."""
        cero = {**escena.curva.cero, "fuente": "pieza_de_menor_dosis", "detalle": "la pieza 2 (50 cGy, la de menor dosis): solo guía"}
        rara = dataclasses.replace(escena.curva, cero=cero)
        assert rara.estado("G") == "válida"
        assert _pm().base_de_la_capa(rara, "G", escena.od.piso, escena.cadena) == (BASE_OD, CERO_GUIA.format(nombre="verde", detalle=cero["detalle"]))

    def test_el_cero_de_la_virgen_montada_si_pasa(self, escena):
        cero = {**escena.curva.cero, "fuente": "pelicula_virgen"}
        assert _pm().base_de_la_capa(dataclasses.replace(escena.curva, cero=cero), "G", escena.od.piso, escena.cadena) == (BASE_DOSIS, None)

    def test_el_piso_de_las_esquinas(self, escena):
        r = _pm().analizar(escena.pelicula, escena.puntos, _P(), modo_piso="automatico")
        assert r.piso.estado == "ok" and r.piso.origen == "automatico"
        assert _pm().base_de_la_capa(escena.curva, "G", r.piso, escena.cadena) == (BASE_OD, PISO_NO_VIRGEN.format(origen="el de las esquinas de la película"))

    def test_el_piso_del_punto_marcado(self, escena):
        piso = dataclasses.replace(escena.od.piso, origen="manual")
        assert _pm().base_de_la_capa(escena.curva, "G", piso, escena.cadena) == (BASE_OD, PISO_NO_VIRGEN.format(origen="el del punto marcado"))

    def test_sin_piso(self, escena):
        assert _pm().base_de_la_capa(escena.curva, "G", None, escena.cadena) == (BASE_OD, PISO_NO_VIRGEN.format(origen="no se midió"))
        sin = dataclasses.replace(escena.od.piso, estado="no medible: no hay película virgen de referencia")
        assert _pm().base_de_la_capa(escena.curva, "G", sin, escena.cadena) == (BASE_OD, PISO_NO_VIRGEN.format(origen="no se midió"))

    def test_sin_cadena(self, escena):
        assert _pm().base_de_la_capa(escena.curva, "G", escena.od.piso, None) == (BASE_OD, SIN_CADENA)

    @pytest.mark.parametrize("cambio", [{"bits": 8}, {"dpi": 150.0}, {"formato": "PNG"}, {"equipo": "EPSON WF-6590"}])
    def test_otra_cadena(self, escena, cambio):
        otra = {**escena.cadena, **cambio}
        esperado = OTRA_CADENA.format(pelicula=texto_de_la_cadena(otra), curva=texto_de_la_cadena(escena.curva.cadena))
        assert _pm().base_de_la_capa(escena.curva, "G", escena.od.piso, otra) == (BASE_OD, esperado)

    def test_la_meseta_fuera_del_rango(self, escena):
        corta = calibrar(dosis=(0, 25, 50, 75, 100, 125, 150, 200))
        assert corta.estado("G") == "válida" and corta.rango("G") == 200.0
        x = 0.4
        esperado = RANGO.format(x=x, nombre="verde", maxima=corta.capas["G"]["netod_maxima"], rango=200.0)
        assert _pm().base_de_la_capa(corta, "G", escena.od.piso, escena.cadena, netod_meseta=x) == (BASE_OD, esperado)
        assert _pm().base_de_la_capa(corta, "G", escena.od.piso, escena.cadena, netod_meseta=corta.capas["G"]["netod_maxima"]) == (BASE_DOSIS, None), "en el borde del rango no se extrapola: vale"

    def test_en_el_analisis_la_meseta_fuera_del_rango_deja_la_capa_sin_numeros(self, escena):
        corta = calibrar(dosis=(0, 25, 50, 75, 100, 125, 150, 200))
        do = _pm().analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=escena.ref, curva=corta, cadena=escena.cadena)
        m = do.capas["G"]
        assert not m.ok and m.base == BASE_OD and m.motivo_de_la_base.startswith("la meseta (netOD ") and m.estado == PREFIJO + m.motivo_de_la_base
        assert m.crossplane.fwhm_mm is None and m.inplane.fwhm_mm is None and m.dosis_meseta_cgy is None and all(v is None for v in m.coincidencia_mm.values())
        assert _pm().valores_medidos(do, "G")["fwhm_crossplane_mm"] is None
        barrido = _pm().barrido(do)
        assert not barrido.ejes["crossplane"].capas["G"].ok and barrido.ejes["crossplane"].capas["G"].estado == m.estado, "una capa sin dosis tampoco se barre en dosis"

    def test_en_el_analisis_cada_capa_que_no_pasa_dice_su_motivo_y_no_trae_numeros(self, escena):
        mala = con_capa(escena.curva, "B", estado="no válida: datos no monótonos: la pieza de 300 cGy tiene menos densidad óptica que la de 200 cGy")
        do = _pm().analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=escena.ref, curva=mala, cadena=escena.cadena)
        b = do.capas["B"]
        assert b.estado == PREFIJO + NO_VALIDA.format(nombre="azul", estado=mala.estado("B")) and b.base == BASE_OD and b.piso is None
        assert b.crossplane.fwhm_mm is None and b.dosis_meseta_cgy is None
        assert do.capas["G"].ok and do.capas["G"].base == BASE_DOSIS, "las demas capas se miden"
        d = do.como_dict()["capas"]["B"]
        assert d["base"] == BASE_OD and d["motivo_de_la_base"] == NO_VALIDA.format(nombre="azul", estado=mala.estado("B"))

    def test_sin_curva_el_analisis_en_dosis_no_mide_ninguna_capa(self, escena):
        do = _pm().analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=escena.ref)
        assert not do.ok and do.estado == _pm().MOTIVO_NINGUNA_CAPA
        for c in TODAS:
            assert do.capas[c].estado == PREFIJO + SIN_CURVA and do.capas[c].base == BASE_OD


# ===================================================================================================== (e) la banda en dosis

class TestLaBandaEnDosisEsLaImagenConvertida:
    def test_los_valores_de_la_banda_llevan_la_media_de_la_dosis_de_cada_pixel(self, escena):
        pm = _pm()
        r = escena.do
        for c in ("G", "gris"):
            cc = pm.curva_de_la_capa(escena.curva, c)
            capa = r.girada.capa(c)
            piso = r.capas[c].piso
            for eje in EJES:
                perfil = pm.perfil_central(capa, eje, _P(BASE_DOSIS), base=BASE_DOSIS, curva=cc, piso=piso)
                datos = capa.datos if eje == "crossplane" else capa.datos.T
                a, b = perfil.filas_px[0] - (capa.origen[1] if eje == "crossplane" else capa.origen[0]), perfil.filas_px[1] - (capa.origen[1] if eje == "crossplane" else capa.origen[0])
                x = np.log10(piso) - np.log10(np.maximum(datos[a:b].astype(np.float64), VP_MINIMO))
                media = (cc.curva.capas[c]["parametros"]["a"] * x + cc.curva.capas[c]["parametros"]["b"] * np.abs(x) ** cc.curva.capas[c]["parametros"]["n"] * np.sign(x)).mean(axis=0)
                dosis_del_perfil = pm.valores_en_la_base(BASE_DOSIS, perfil.valores, piso, cc)
                bien = np.isfinite(perfil.valores)
                assert bien.sum() > 1000
                assert np.allclose(dosis_del_perfil[bien], media[bien], rtol=1e-9, atol=1e-7), (c, eje)

    def test_la_banda_en_netod_no_es_la_de_dosis(self, escena):
        pm = _pm()
        capa = escena.do.girada.capa("G")
        piso = escena.do.capas["G"].piso
        en_dosis = pm.perfil_central(capa, "crossplane", _P(BASE_DOSIS), base=BASE_DOSIS, curva=pm.curva_de_la_capa(escena.curva, "G"), piso=piso).valores
        assert np.array_equal(escena.do.capas["G"].crossplane.perfil.valores, en_dosis, equal_nan=True), "el corte central del analisis en dosis promedia en dosis"

    def test_la_banda_en_dosis_pide_el_piso(self, escena):
        pm = _pm()
        with pytest.raises(ValueError, match="necesita el nivel de piso"):
            pm.perfil_central(escena.do.girada.capa("G"), "crossplane", _P(BASE_DOSIS), base=BASE_DOSIS, curva=pm.curva_de_la_capa(escena.curva, "G"))

    @pytest.mark.parametrize("clave", sorted(CLICS))
    def test_en_las_peliculas_reales_los_bordes_son_los_de_la_imagen_convertida(self, escena, clave):
        """La imagen girada CONVERTIDA PIXEL A PIXEL a dosis (con la curva de la escena, ensanchada para cubrir sus mesetas: aqui se prueba la conversion, no la cadena) y medida en valor de pixel con la
        escala que lleva la dosis 0 al piso y la de la meseta a la meseta: sin apartar la tinta (`delta_tinta` enorme en las dos rutas) da los MISMOS bordes que la base dosis (1e-6 mm: la banda, la meseta y
        el suavizado son los de la imagen convertida, CD6-D3); con la tinta de siempre, a 0.02 mm (la tinta se aparta en niveles en el motor y en esas unidades en la convertida; medido el 31-10: 0.0154 mm
        en el peor de los 48, EPSON028 verde inplane; la misma tolerancia que OD.1 (c))."""
        pm = _pm()
        ruta = _corpus.pelicula(clave)
        if ruta is None:
            pytest.skip(f"HI-0: la pelicula real {clave} no esta")
        r = pm.analizar(_pel().leer_pelicula(Path(ruta).read_bytes()), CLICS[clave], _P(), modo_piso="automatico")
        curva = ancha(escena.curva)
        for c in ("G", "B", "gris"):
            cc = pm.curva_de_la_capa(curva, c)
            original = r.girada.capa(c)
            piso = r.capas[c].piso
            x = np.log10(piso) - np.log10(np.maximum(original.datos.astype(np.float64), VP_MINIMO))
            p = curva.capas[c]["parametros"]
            dosis = p["a"] * x + p["b"] * np.sign(x) * np.abs(x) ** p["n"]
            for i, eje in enumerate(EJES):
                for tinta, tolerancia in ((1e9, 1e-6), (None, 0.02)):
                    cambios = {} if tinta is None else {"delta_tinta": tinta}
                    perfil = pm.perfil_central(original, eje, _P(BASE_DOSIS, **cambios), base=BASE_DOSIS, curva=cc, piso=piso)
                    en_dosis = pm.medir_perfil(perfil, r.girada.cruce[i], piso, BASE_DOSIS, _P(BASE_DOSIS, **cambios), r.bordes_luz_px[eje], r.geometria.reticulo_girado[i], curva=cc)
                    assert en_dosis.ok, (clave, c, eje, en_dosis.estado)
                    dosis_meseta = float(cc.dosis(math.log10(piso / en_dosis.meseta)))
                    capa_c = dataclasses.replace(original, datos=(piso - (piso - en_dosis.meseta) * dosis / dosis_meseta).astype(np.float32))
                    m = pm.medir_perfil(pm.perfil_central(capa_c, eje, _P(BASE_VP, **cambios)), r.girada.cruce[i], piso, BASE_VP, _P(BASE_VP, **cambios), r.bordes_luz_px[eje],
                                        r.geometria.reticulo_girado[i])
                    assert m.ok, (clave, c, eje, m.estado)
                    for b_d, b_c in zip(en_dosis.bordes_rad_px, m.bordes_rad_px):
                        assert abs(b_d - b_c) * TAM <= tolerancia, (clave, c, eje, tinta, b_d, b_c)
        del r
        gc.collect()


# ===================================================================================================== (f-bis) la regla del boton y la curva efectiva

class TestLaReglaDelBoton:
    def test_con_las_cinco_condiciones_se_puede(self, escena):
        for c in TODAS:
            assert _pm().se_puede_pasar_a_dosis(escena.od, efectiva_de(escena.curva), c, escena.cadena) == (True, None), c

    def test_sin_curva_dice_el_motivo_de_la_curva_efectiva(self, escena):
        pm = _pm()
        sin = pm.curva_efectiva([], escena.cadena)
        assert pm.se_puede_pasar_a_dosis(escena.od, sin, "G", escena.cadena) == (False, sin.motivo) and sin.motivo.startswith(SIN_CURVA)

    def test_condicion_1_la_curva_de_la_capa_no_es_valida(self, escena):
        mala = con_capa(escena.curva, "G", estado="incompleta: quedan 4 dosis en el rango útil (hacen falta 6)")
        assert _pm().se_puede_pasar_a_dosis(escena.od, efectiva_de(mala), "G", escena.cadena) == (False, NO_VALIDA.format(nombre="verde", estado=mala.estado("G")))

    def test_condicion_1_mira_la_capa_reportada_y_no_otra(self, escena):
        mala = con_capa(escena.curva, "R", estado="no válida: el ajuste no converge")
        assert _pm().se_puede_pasar_a_dosis(escena.od, efectiva_de(mala), "G", escena.cadena) == (True, None)
        assert _pm().se_puede_pasar_a_dosis(escena.od, efectiva_de(mala), "R", escena.cadena)[0] is False

    def test_condicion_2_el_piso_de_las_esquinas(self, escena):
        r = _pm().analizar(escena.pelicula, escena.puntos, _P(), modo_piso="automatico")
        assert _pm().se_puede_pasar_a_dosis(r, efectiva_de(escena.curva), "G", escena.cadena) == (False, PISO_NO_VIRGEN.format(origen="el de las esquinas de la película"))

    def test_condicion_3_otra_cadena(self, escena):
        otra = {**escena.cadena, "bits": 8}
        esperado = OTRA_CADENA.format(pelicula=texto_de_la_cadena(otra), curva=texto_de_la_cadena(escena.curva.cadena))
        assert _pm().se_puede_pasar_a_dosis(escena.od, efectiva_de(escena.curva), "G", otra) == (False, esperado)

    def test_condicion_4_la_meseta_fuera_del_rango(self, escena):
        corta = calibrar(dosis=(0, 25, 50, 75, 100, 125, 150, 200))
        m = escena.od.capas["G"]
        x = max(math.log10(getattr(m, e).piso / getattr(m, e).meseta) for e in EJES)
        esperado = RANGO.format(x=x, nombre="verde", maxima=corta.capas["G"]["netod_maxima"], rango=200.0)
        assert _pm().se_puede_pasar_a_dosis(escena.od, efectiva_de(corta), "G", escena.cadena) == (False, esperado)

    def test_condicion_4_la_juzga_la_meseta_mas_oscura_de_los_dos_perfiles(self, escena):
        """CD6-D6 (CD6-REV-PRU-03): la condicion 4 se juzga con la meseta MAS OSCURA (la mayor netOD) de los dos perfiles, porque en dosis un solo perfil fuera del rango deja la capa entera «no medible en dosis». En la
        placa de la escena los dos dan la misma meseta (a 1e-9) y ni el eje ni max/min se notaban; aqui uno queda dentro del rango y el otro fuera, en los dos ordenes: el boton se apaga y el motivo cita la netOD
        del mas oscuro (la meseta mas clara, o un solo eje, lo dejarian encendido en uno de los dos casos)."""
        pm = _pm()
        maxima = escena.curva.capas["G"]["netod_maxima"]
        fuera, dentro = maxima + 0.05, maxima - 0.05
        for eje_fuera in EJES:
            r = con_mesetas(escena.od, "G", **{eje_fuera: fuera, ("inplane" if eje_fuera == "crossplane" else "crossplane"): dentro})
            medida = r.capas["G"]
            x = max(math.log10(getattr(medida, e).piso / getattr(medida, e).meseta) for e in EJES)
            assert x == pytest.approx(fuera, abs=1e-9), "el perfil mas oscuro es el que se puso fuera del rango"
            esperado = RANGO.format(x=x, nombre="verde", maxima=maxima, rango=escena.curva.rango("G"))
            assert pm.se_puede_pasar_a_dosis(r, efectiva_de(escena.curva), "G", escena.cadena) == (False, esperado), eje_fuera
        los_dos_dentro = con_mesetas(escena.od, "G", crossplane=dentro, inplane=dentro)
        assert pm.se_puede_pasar_a_dosis(los_dos_dentro, efectiva_de(escena.curva), "G", escena.cadena) == (True, None)

    def test_condicion_5_la_curva_guia(self, escena):
        guia = calibrar(cero=False)
        assert _pm().se_puede_pasar_a_dosis(escena.od, efectiva_de(guia), "G", escena.cadena) == (False, GUIA.format(nombre="verde", dosis=50))

    def test_la_regla_se_juzga_sobre_el_analisis_en_netod(self, escena):
        pm = _pm()
        with pytest.raises(ValueError, match="se juzga sobre el análisis en «densidad óptica neta»"):
            pm.se_puede_pasar_a_dosis(escena.do, efectiva_de(escena.curva), "G", escena.cadena)
        with pytest.raises(ValueError, match="es una `CurvaEfectiva`"):
            pm.se_puede_pasar_a_dosis(escena.od, escena.curva, "G", escena.cadena)
        with pytest.raises(ValueError, match="La capa es una de"):
            pm.se_puede_pasar_a_dosis(escena.od, efectiva_de(escena.curva), "verde", escena.cadena)

    def test_la_regla_entera_esta_escrita_para_la_ayuda_del_boton(self):
        texto = _pm().CONDICIONES_PARA_PASAR_A_DOSIS
        for pedazo in ("«válida»", "pieza de 0 cGy", "película virgen montada", "piso", "cadena de captura", "rango útil", "no se extrapola"):
            assert pedazo in texto, pedazo


class TestLaCurvaEfectiva:
    @staticmethod
    def registro(curva, id_, lote="L", fecha="2026-10-30"):
        return {"id": id_, "lote": lote, "fecha_irradiacion": fecha, "ajuste": curva.como_dict()}

    def test_elige_la_primera_valida_de_la_cadena_de_la_pelicula(self, escena):
        pm = _pm()
        otra = dataclasses.replace(escena.curva, cadena={**escena.curva.cadena, "bits": 8})
        lista = [self.registro(otra, 3, "nueva", "2026-10-31"), self.registro(escena.curva, 2, "media", "2026-10-29"), self.registro(escena.curva, 1, "vieja", "2026-10-01")]
        e = pm.curva_efectiva(lista, escena.cadena)
        assert (e.id, e.lote, e.fecha_irradiacion, e.motivo) == (2, "media", "2026-10-29", None)
        assert e.curva.como_dict() == escena.curva.como_dict()

    def test_ninguna_si_la_unica_valida_es_de_otra_cadena_y_el_motivo_dice_la_regla(self, escena):
        pm = _pm()
        otra = dataclasses.replace(escena.curva, cadena={**escena.curva.cadena, "bits": 8})
        e = pm.curva_efectiva([self.registro(otra, 3, "nueva", "2026-10-31")], escena.cadena)
        assert e.curva is None and e.id is None
        assert e.motivo == (f"{SIN_CURVA} para la cadena de captura de esta película ({texto_de_la_cadena(escena.cadena)}): hay 1 calibración vigente con una capa válida, de otra cadena (la más "
                            f"reciente, el lote «nueva» irradiado el 2026-10-31: {texto_de_la_cadena(otra.cadena)}) ({REGLA})")

    def test_sin_calibraciones(self, escena):
        e = _pm().curva_efectiva([], escena.cadena)
        assert e.curva is None and e.motivo == f"{SIN_CURVA}: no hay ninguna calibración vigente con una capa válida (se hace con «Curva de dosis...») ({REGLA})"

    def test_una_sin_capa_valida_no_se_elige_aunque_sea_de_la_cadena(self, escena):
        """Defensa: la lista viene de `vigentes_validas` (que ya filtra), pero el motor no confia en quien llama."""
        pm = _pm()
        ninguna = escena.curva
        for c in TODAS:
            ninguna = con_capa(ninguna, c, estado="incompleta: falta la película virgen (0 cGy)")
        e = pm.curva_efectiva([self.registro(ninguna, 5), self.registro(escena.curva, 4)], escena.cadena)
        assert e.id == 4

    def test_una_copia_danada_se_salta_y_se_cuenta(self, escena):
        pm = _pm()
        danada = {"id": 9, "lote": "x", "fecha_irradiacion": "2026-10-31", "ajuste": {"version": "CD-1"}}
        assert pm.curva_efectiva([danada, self.registro(escena.curva, 4)], escena.cadena).id == 4
        e = pm.curva_efectiva([danada], escena.cadena)
        assert e.curva is None and e.motivo == (f"{SIN_CURVA}: no hay ninguna calibración vigente con una capa válida (se hace con «Curva de dosis...»); 1 con la copia de la curva dañada, que no "
                                                f"se puede leer ({REGLA})")

    def test_sin_cadena(self, escena):
        e = _pm().curva_efectiva([self.registro(escena.curva, 4)], None)
        assert e.curva is None and e.motivo == f"{SIN_CURVA}: no se conoce la cadena de captura de la película ({REGLA})"

    @pytest.mark.parametrize("validas", [("G",), ("R",), ("gris",), ("R", "B"), ("G", "B", "gris")], ids="_".join)
    def test_una_calibracion_con_al_menos_una_capa_valida_se_elige(self, escena, validas):
        """La regla dice «con al menos una capa válida», no con las cuatro (CD6-REV-PRU-02): una calibracion real con una capa saturada (la roja) o incompleta sigue siendo la vigente para las demas, y el boton juzga
        despues la capa reportada con ESA curva. Las curvas de las demas pruebas tenian las cuatro capas validas o ninguna, y exigir las cuatro (`all` en lugar de `any`) no lo notaba."""
        pm = _pm()
        curva = escena.curva
        for c in TODAS:
            if c not in validas:
                curva = con_capa(curva, c, estado="no válida: el ajuste no converge")
        e = pm.curva_efectiva([self.registro(curva, 4)], escena.cadena)
        assert e.id == 4 and e.curva is not None and e.motivo is None
        for c in TODAS:
            esperado = (True, None) if c in validas else (False, NO_VALIDA.format(nombre=NOMBRE[c], estado=curva.estado(c)))
            assert pm.se_puede_pasar_a_dosis(escena.od, e, c, escena.cadena) == esperado, c


# ===================================================================================================== CD6-D5: el ORDEN de la regla

MALA = "no válida: el ajuste no converge"
CERO_DE_GUIA = "la pieza 2 (50 cGy, la de menor dosis): solo guía"
NO_MEDIDA_EN_NETOD = "no medible: la meseta está en el negro del escáner"
PASOS_DE_LA_REGLA = ("sin_curva", "curva_no_valida", "cero_que_no_es_de_0_cgy", "piso_de_las_esquinas", "otra_cadena", "meseta_fuera_del_rango")
PASOS_DEL_BOTON = PASOS_DE_LA_REGLA[:5] + ("capa_no_medida",) + PASOS_DE_LA_REGLA[5:]


def rotas_desde(escena, pasos):
    """El estado de la capa verde (curva, piso, cadena, netOD de la meseta, si se midio en netOD) con TODOS los `pasos` rotos a la vez."""
    e = types.SimpleNamespace(curva=escena.curva, piso=escena.od.piso, cadena=escena.cadena, netod=None, no_medida=None)
    for paso in pasos:
        if paso == "sin_curva":
            e.curva = None
        elif paso == "curva_no_valida" and e.curva is not None:
            e.curva = con_capa(e.curva, "G", estado=MALA)
        elif paso == "cero_que_no_es_de_0_cgy" and e.curva is not None:
            e.curva = dataclasses.replace(e.curva, cero={**e.curva.cero, "fuente": "pieza_de_menor_dosis", "detalle": CERO_DE_GUIA})
        elif paso == "piso_de_las_esquinas":
            e.piso = dataclasses.replace(e.piso, origen="automatico")
        elif paso == "otra_cadena":
            e.cadena = {**e.cadena, "bits": 8}
        elif paso == "capa_no_medida":
            e.no_medida = NO_MEDIDA_EN_NETOD
        elif paso == "meseta_fuera_del_rango":
            e.netod = escena.curva.capas["G"]["netod_maxima"] + 0.1
    return e


def motivo_del_paso(escena, paso, e):
    """El motivo EXACTO que dice la regla cuando el primer paso roto es `paso`."""
    return {
        "sin_curva": SIN_CURVA,
        "curva_no_valida": NO_VALIDA.format(nombre="verde", estado=MALA),
        "cero_que_no_es_de_0_cgy": CERO_GUIA.format(nombre="verde", detalle=CERO_DE_GUIA),
        "piso_de_las_esquinas": PISO_NO_VIRGEN.format(origen="el de las esquinas de la película"),
        "otra_cadena": OTRA_CADENA.format(pelicula=texto_de_la_cadena(e.cadena), curva=texto_de_la_cadena(escena.curva.cadena)),
        "capa_no_medida": NO_MEDIDA.format(nombre="verde", estado=NO_MEDIDA_EN_NETOD),
        "meseta_fuera_del_rango": RANGO.format(x=e.netod, nombre="verde", maxima=escena.curva.capas["G"]["netod_maxima"], rango=escena.curva.rango("G")),
    }[paso]


class TestElOrdenDeLaRegla:
    """CD6-D5 y DA-92 («el motivo de la primera que falla», CD6-REV-PRU-05): con VARIAS condiciones rotas a la vez la regla dice la primera, en este orden: no hay curva; la curva de la capa no es valida; su cero no
    es una pieza de 0 cGy ni la virgen montada; el piso no es el de la virgen; la cadena no es la de la calibracion; (solo en el boton: la capa no se midio en netOD); la meseta pasa el rango util. Cada caso rompe,
    de una vez, un paso y TODOS los que le siguen: el motivo tiene que ser el de ese paso. Las pruebas de cada motivo (TestCadaMotivoDeLaRegla, TestLaReglaDelBoton) rompen UNA condicion y no ven el orden: dos
    condiciones vecinas cambiadas de lugar cambian el motivo de un solo caso de aqui."""

    @pytest.mark.parametrize("desde", range(len(PASOS_DE_LA_REGLA)), ids=PASOS_DE_LA_REGLA)
    def test_base_de_la_capa_dice_la_primera_condicion_que_falla(self, escena, desde):
        e = rotas_desde(escena, PASOS_DE_LA_REGLA[desde:])
        assert _pm().base_de_la_capa(e.curva, "G", e.piso, e.cadena, netod_meseta=e.netod) == (BASE_OD, motivo_del_paso(escena, PASOS_DE_LA_REGLA[desde], e))

    @pytest.mark.parametrize("desde", range(len(PASOS_DEL_BOTON)), ids=PASOS_DEL_BOTON)
    def test_el_boton_dice_la_primera_condicion_que_falla(self, escena, desde):
        pm = _pm()
        paso = PASOS_DEL_BOTON[desde]
        e = rotas_desde(escena, PASOS_DEL_BOTON[desde:])
        resultado = dataclasses.replace(escena.od, piso=e.piso)
        if e.netod is not None:
            resultado = con_mesetas(resultado, "G", crossplane=e.netod, inplane=e.netod)
        if e.no_medida is not None:
            medida = resultado.capas["G"]
            resultado = dataclasses.replace(resultado, capas={**resultado.capas, "G": dataclasses.replace(medida, estado=e.no_medida)})
        efectiva = pm.curva_efectiva([], e.cadena) if e.curva is None else efectiva_de(e.curva)
        esperado = efectiva.motivo if paso == "sin_curva" else motivo_del_paso(escena, paso, e)
        assert pm.se_puede_pasar_a_dosis(resultado, efectiva, "G", e.cadena) == (False, esperado)


# ===================================================================================================== (g) el rojo recortado

@pytest.fixture(scope="module")
def recortada():
    """La placa de PF.0 de siempre (el rojo en el negro del escaner, la verde en 0.73 de netOD) a 16 bits, su analisis en netOD y en dosis con la curva de la escena."""
    pm, pel = _pm(), _pel()
    placa = gen.generar("tiff", bits=16, variante="A", theta_deg=0.4, seed=1)
    pelicula = pel.leer_pelicula(placa.datos)
    puntos = [placa.verdad.marcas_px[k] for k in ("UL", "UR", "DR", "DL", "C")]
    cadena = pm.cadena_de_la_pelicula(placa.datos, pelicula)
    ref = referencia(16)
    yield types.SimpleNamespace(cadena=cadena, od=pm.analizar(pelicula, puntos, _P(), modo_piso="virgen", referencia_virgen=ref),
                                curva=calibrar(), pelicula=pelicula, puntos=puntos, ref=ref)
    gc.collect()


class TestElRojoRecortadoSigueNoMedible:
    def test_en_dosis_el_rojo_recortado_es_no_medible(self, escena, recortada):
        pm = _pm()
        do = pm.analizar(recortada.pelicula, recortada.puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=recortada.ref, curva=recortada.curva, cadena=recortada.cadena)
        rojo = do.capas["R"]
        assert not rojo.ok and pm.MOTIVO_MESETA_RECORTADA in rojo.estado and rojo.crossplane.fwhm_mm is None, rojo.estado

    def test_el_boton_lo_dice(self, recortada):
        pm = _pm()
        rojo = recortada.od.capas["R"]
        assert not rojo.ok
        assert pm.se_puede_pasar_a_dosis(recortada.od, efectiva_de(recortada.curva), "R", recortada.cadena) == (False, NO_MEDIDA.format(nombre="roja", estado=rojo.estado))


    def test_con_la_curva_roja_no_valida_el_boton_dice_primero_la_curva(self, recortada):
        """CD6-D5 (el orden): la curva de la capa se juzga ANTES que la medida en netOD; con la roja recortada Y su curva no valida, el motivo es el de la curva (la mutacion M08 del pre-vuelo, que
        juzgaba la curva de otra capa, sobrevivia sin esta prueba: la segunda llamada de la regla, con la meseta, la tapaba)."""
        pm = _pm()
        mala = con_capa(recortada.curva, "R", estado="no válida: el ajuste no converge")
        assert pm.se_puede_pasar_a_dosis(recortada.od, efectiva_de(mala), "R", recortada.cadena) == (False, NO_VALIDA.format(nombre="roja", estado="no válida: el ajuste no converge"))


# ===================================================================================================== el aviso de la pelicula virgen y el parametro 42

class TestElAvisoDeLaPeliculaVirgen:
    @pytest.mark.parametrize("factor", [1.03, 0.97], ids=["mas_clara", "mas_oscura"])
    def test_una_virgen_que_difiere_mas_del_2_por_ciento_avisa_sin_bloquear(self, escena, factor):
        """Por la diferencia ABSOLUTA: una virgen mas OSCURA que el cero de la curva (otro lote, un escaneo con menos luz) es tan distinta como una mas clara (CD6-REV-PRU-01: sin el valor absoluto el caso de -3 %
        no avisaba y ninguna prueba lo notaba, porque todas usaban virgenes mas claras)."""
        pm = _pm()
        valores = dict(PISO_DE_LA_PLACA, G=PISO_DE_LA_PLACA["G"] * factor)
        do = pm.analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=referencia(16, valores), curva=escena.curva, cadena=escena.cadena)
        assert len(do.avisos_de_la_dosis) == 1 and do.capas["G"].ok, do.avisos_de_la_dosis
        i0 = escena.curva.cero["capas"]["G"]["i0"]
        dif = 100.0 * (valores["G"] - i0) / i0
        assert (dif > 0) == (factor > 1.0) and abs(abs(dif) - 3.0) < 0.01, dif
        assert do.avisos_de_la_dosis[0] == (f"La película virgen del análisis difiere {dif:+.2f} % del cero de la curva en la capa verde (piso {valores['G']:.2f} contra I0 {i0:.2f} [nivel]; se avisa a más "
                                            f"de 2 %): la netOD del análisis y la de la curva no salen de la misma película virgen (otro lote u otra sesión de escaneo).")

    @pytest.mark.parametrize("origen", ["automatico", "sin_modo_ni_referencia", "manual"])
    def test_sin_pelicula_virgen_en_el_analisis_no_hay_nada_que_comparar(self, escena, origen):
        """CD6-REV-P1: el aviso compara la PELICULA VIRGEN del analisis con el cero de la curva; si el piso del analisis no es el de una virgen (las esquinas de la pelicula, o el punto marcado) no hay virgen que
        comparar, y el aviso no puede decir «La pelicula virgen del analisis difiere ...» (la regla de la base ya deja esas capas «no medible en dosis: el piso no es el de la pelicula virgen», y el aviso
        decia lo contrario). «sin_modo_ni_referencia» es el camino de la app cuando no se cargo la virgen: el modo por omision es «virgen» y sin referencia cae a las esquinas (`modo_efectivo`). Con el mismo
        cero la virgen montada SI avisa (el control)."""
        pm = _pm()
        cero = copy.deepcopy(escena.curva.cero)
        for c in TODAS:
            cero["capas"][c]["i0"] *= 1.05                    # el cero de otra sesion de escaneo de la virgen: a una virgen montada le avisaria en las cuatro capas
        otra = dataclasses.replace(escena.curva, cero=cero)
        assert len(pm.avisos_de_la_virgen(otra, escena.od.piso, 2.0)) == 4, "el control: la virgen montada SI avisa"
        if origen in ("automatico", "sin_modo_ni_referencia"):
            modo = {"modo_piso": "automatico"} if origen == "automatico" else {}
            do = pm.analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS), curva=otra, cadena=escena.cadena, **modo)
            assert do.piso.estado == "ok" and do.piso.origen == "automatico"
            for c in TODAS:
                assert do.capas[c].estado == PREFIJO + PISO_NO_VIRGEN.format(origen="el de las esquinas de la película"), c
            assert do.avisos_de_la_dosis == () and do.como_dict()["avisos_de_la_dosis"] == []
            piso = do.piso
        else:
            piso = dataclasses.replace(escena.od.piso, origen="manual")
        assert pm.avisos_de_la_virgen(otra, piso, 2.0) == ()

    def test_el_aviso_y_la_regla_de_la_base_coinciden_en_cual_piso_es_el_de_la_virgen(self, escena):
        """Una operacion, una definicion: «el piso es el de la pelicula virgen» lo juzgan la regla de la base (condicion 2) y el aviso, cada uno por su lado; la convergencia de los dos caminos se afirma con prueba
        (CD6-REV-P1) para todo piso posible: sin piso, un piso que no se midio, el de las esquinas, el del punto marcado y la virgen montada."""
        pm = _pm()
        cero = copy.deepcopy(escena.curva.cero)
        for c in TODAS:
            cero["capas"][c]["i0"] *= 1.05
        otra = dataclasses.replace(escena.curva, cero=cero)
        pisos = {"sin piso": None, "sin medir": dataclasses.replace(escena.od.piso, estado="no medible: no hay película virgen de referencia"),
                 "esquinas": dataclasses.replace(escena.od.piso, origen="automatico"), "punto marcado": dataclasses.replace(escena.od.piso, origen="manual"), "virgen montada": escena.od.piso}
        for nombre, piso in pisos.items():
            _, motivo = pm.base_de_la_capa(otra, "G", piso, escena.cadena)          # con el cero y la cadena en orden, lo unico que puede fallar es el piso
            assert motivo is None or motivo.startswith("el piso no es el de la película virgen"), (nombre, motivo)
            assert bool(pm.avisos_de_la_virgen(otra, piso, 2.0)) == (motivo is None), nombre

    def test_con_un_1_por_ciento_no_avisa_y_el_parametro_42_manda(self, escena):
        pm = _pm()
        valores = dict(PISO_DE_LA_PLACA, G=PISO_DE_LA_PLACA["G"] * 1.01)
        assert pm.analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=referencia(16, valores), curva=escena.curva,
                           cadena=escena.cadena).avisos_de_la_dosis == ()
        estricto = pm.analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS, diferencia_virgen_maxima_pct=0.5), modo_piso="virgen", referencia_virgen=referencia(16, valores),
                               curva=escena.curva, cadena=escena.cadena)
        assert len(estricto.avisos_de_la_dosis) == 1 and "se avisa a más de 0.5 %" in estricto.avisos_de_la_dosis[0]

    def test_un_registro_sin_el_parametro_42_se_mide_en_dosis_con_el_de_fabrica(self, escena):
        P = _P(BASE_DOSIS)
        del P["diferencia_virgen_maxima_pct"]
        do = _pm().analizar(escena.pelicula, escena.puntos, P, modo_piso="virgen", referencia_virgen=escena.ref, curva=escena.curva, cadena=escena.cadena)
        assert do.parametros["diferencia_virgen_maxima_pct"] == 2.0 and do.capas["G"].crossplane.fwhm_mm == escena.do.capas["G"].crossplane.fwhm_mm

    def test_el_parametro_42_tiene_nombre_unidad_y_motivo_y_no_lo_pide_analizar(self):
        pm = _pm()
        p = pm.PARAMETROS["diferencia_virgen_maxima_pct"]
        assert p["valor"] == 2.0 and p["unidad"] == "%" and len(p["motivo"]) > 100
        assert len(pm.VALORES_DE_LA_GEOMETRIA) == 42 and list(pm.VALORES_DE_LA_GEOMETRIA)[-1] == "diferencia_virgen_maxima_pct"
        assert "diferencia_virgen_maxima_pct" not in pm.CLAVES_QUE_PIDE_ANALIZAR


# ===================================================================================================== las defensas (la cobertura de lineas del pre-vuelo: cada una con una prueba cuyo efecto es ESA defensa)

class TestLasDefensas:
    def test_un_analisis_en_dosis_que_no_llega_a_medir_dice_su_curva_y_su_cadena(self, escena):
        """Sin la pelicula virgen el piso no se mide: el resultado en dosis sale por `sin_medir` y aun asi trae la curva y la cadena con que se pidio (CD.7 dice cual)."""
        do = _pm().analizar(escena.pelicula, escena.puntos, _P(BASE_DOSIS), modo_piso="virgen", referencia_virgen=None, curva=escena.curva, cadena=escena.cadena)
        assert not do.ok and do.piso.estado.startswith("no medible") and do.curva is escena.curva and do.cadena == escena.cadena
        assert do.como_dict()["curva"] == escena.curva.como_dict()

    def test_una_base_que_no_existe_en_los_parametros(self, escena):
        with pytest.raises(ValueError, match="no está implementada"):
            _pm().analizar(escena.pelicula, escena.puntos, _P("dosis absoluta"), modo_piso="virgen", referencia_virgen=escena.ref)

    def test_la_curva_de_la_capa_rechaza_lo_que_no_es(self, escena):
        pm = _pm()
        with pytest.raises(ValueError, match="es una `CurvaDeDosis`"):
            pm.curva_de_la_capa(escena.curva.como_dict(), "G")
        with pytest.raises(ValueError, match="La capa es una de"):
            pm.curva_de_la_capa(escena.curva, "verde")
        sin = con_capa(escena.curva, "B", parametros=None, estado="no válida: el ajuste no converge")
        with pytest.raises(ValueError, match="La curva de la capa azul no tiene parámetros: no válida: el ajuste no converge."):
            pm.curva_de_la_capa(sin, "B")
        with pytest.raises(ValueError, match="La capa es una de"):
            pm.base_de_la_capa(escena.curva, "verde", escena.od.piso, escena.cadena)

    def test_una_capa_valida_sin_rango_util_no_pasa_a_dosis(self, escena):
        rara = con_capa(escena.curva, "G", netod_maxima=None, rango_cgy=None)
        assert _pm().base_de_la_capa(rara, "G", escena.od.piso, escena.cadena, netod_meseta=0.1) == (BASE_OD, "la curva de la capa verde no tiene rango útil")

    def test_el_aviso_se_salta_la_capa_sin_piso_o_sin_i0(self, escena):
        pm = _pm()
        cero = copy.deepcopy(escena.curva.cero)
        cero["capas"]["G"]["i0"] = 0.0
        curva = dataclasses.replace(escena.curva, cero=cero)
        valores = {c: v * 1.10 for c, v in PISO_DE_LA_PLACA.items()}
        piso = pm.analizar(escena.pelicula, escena.puntos, _P(), modo_piso="virgen", referencia_virgen=referencia(16, valores)).piso
        avisos = pm.avisos_de_la_virgen(curva, piso, 2.0)
        assert len(avisos) == 3 and not any("capa verde" in a for a in avisos), avisos
        sin_valor = dataclasses.replace(piso, capas={**piso.capas, "R": dataclasses.replace(piso.capas["R"], mediana=None)})
        assert len(pm.avisos_de_la_virgen(curva, sin_valor, 2.0)) == 2
        assert pm.avisos_de_la_virgen(None, piso, 2.0) == () and pm.avisos_de_la_virgen(curva, None, 2.0) == ()


# ===================================================================================================== la cadena de la pelicula y la estructura

class TestLaCadenaDeLaPelicula:
    def test_es_la_de_cd2_en_la_sintetica(self, escena):
        m = _pel().medir_pieza_uniforme(escena.placa.datos, _P(), "placa.tif", FECHA, escala="declarada")
        assert _pm().cadena_de_la_pelicula(escena.placa.datos) == _cd().cadena_de_captura(m.procedencia) == {"equipo": None, "bits": 16, "dpi": 600.0, "formato": "TIFF"}

    @pytest.mark.parametrize("clave", ["EPSON008_TIF", "EPSON001_JPG"])
    def test_es_la_de_cd2_en_una_pelicula_real_con_su_escaner(self, clave):
        ruta = _corpus.pelicula(clave)
        if ruta is None:
            pytest.skip(f"HI-0: la pelicula real {clave} no esta")
        datos = Path(ruta).read_bytes()
        m = _pel().medir_pieza_uniforme(datos, _P(), "real", FECHA, escala="declarada")
        cadena = _pm().cadena_de_la_pelicula(datos)
        assert cadena == _cd().cadena_de_captura(m.procedencia) and cadena["equipo"], cadena


def _llamadas_de_produccion(nombre):
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
            for nodo in ast.walk(ast.parse(fuente)):
                rel = str(ruta.relative_to(RAIZ)).replace(os.sep, "/")
                # las del motor (por su nombre suelto, en su archivo) y las de quien lo importa (`motor.<nombre>`); `posicion_inicial_braqui.medir_perfil` es OTRA funcion con el mismo nombre
                if isinstance(nodo, ast.Call) and ((isinstance(nodo.func, ast.Name) and nodo.func.id == nombre and rel == "analisisImagenes/placa_mensual.py")
                                                   or (isinstance(nodo.func, ast.Attribute) and nodo.func.attr == nombre)):
                    encontradas.append((rel, nodo))
    return encontradas


class TestEstructura:
    @pytest.mark.parametrize("nombre", ["perfil_central", "medir_perfil"])
    def test_toda_llamada_de_produccion_pasa_la_curva(self, nombre):
        """Tripwire por AST: un llamador que olvide `curva=` mediria en dosis sin curva (ValueError) o, peor, con la de otra capa si alguien la tomara de un nombre de afuera. La curva es la de SU capa
        (`curva=curva`, que en `_medir_la_capa` y `_banda_del_barrido` es `curva_de_la_capa(..., <esa capa>)`)."""
        llamadas = _llamadas_de_produccion(nombre)
        assert len(llamadas) >= 2
        for ruta, nodo in llamadas:
            claves = {k.arg: k.value for k in nodo.keywords}
            assert "curva" in claves and isinstance(claves["curva"], ast.Name) and claves["curva"].id == "curva", f"{ruta} (linea {nodo.lineno}) llama a `{nombre}` sin `curva=curva`"

    def test_la_curva_de_la_capa_del_barrido_es_la_de_la_capa_que_se_barre(self):
        fuente = (RAIZ / "analisisImagenes" / "placa_mensual.py").read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        funcion = next(f for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef) and f.name == "_banda_del_barrido")
        llamadas = [n for n in ast.walk(funcion) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "curva_de_la_capa"]
        assert len(llamadas) == 1 and ast.unparse(llamadas[0].args[1]) == "capa.nombre", [ast.unparse(n) for n in llamadas]

    def test_el_motor_no_lee_la_base_ni_usa_qt(self):
        fuente = (RAIZ / "analisisImagenes" / "placa_mensual.py").read_text(encoding="utf-8")
        modulos = set()
        for nodo in ast.walk(ast.parse(fuente)):
            if isinstance(nodo, ast.Import):
                modulos |= {a.name for a in nodo.names}
            elif isinstance(nodo, ast.ImportFrom):
                modulos.add(nodo.module or "")
        assert not {m for m in modulos if m.split(".")[0] in {"PyQt5", "PyQt6", "services", "data", "ui", "sqlite3"}}, modulos

    def test_los_textos_nuevos_no_llevan_simbolos(self):
        pm = _pm()
        textos = [pm.CONDICIONES_PARA_PASAR_A_DOSIS, pm.REGLA_DE_LA_CURVA, pm.MOTIVO_SIN_CURVA, pm.PREFIJO_NO_MEDIBLE_EN_DOSIS, pm.PARAMETROS["diferencia_virgen_maxima_pct"]["motivo"]]
        textos += list(pm.TEXTO_DEL_ORIGEN_DEL_PISO.values())
        for t in textos:
            assert not set(t) & set(SIMBOLOS), t

    @pytest.mark.parametrize("caso", sorted(PLACAS_DE_PF0))
    def test_la_variante_del_generador_no_cambia_la_placa_de_siempre(self, caso):
        """Obstaculo 5 y CD6-REV-PRU-06: sin `respuestas_netod` el generador da la placa de PF.0 BYTE A BYTE como la daba el de HEAD (el de antes de CD.6): el digest de arriba es el de ESA placa, medido con
        `git show HEAD:tests/_placa_mensual_sintetica.py`. La version anterior de esta prueba comparaba el generador consigo mismo (los argumentos omitidos contra `None` explicito) y pasaba aunque la placa de
        PF.0 cambiara; esa comparacion se conserva, pero lo que fija la placa es el digest."""
        argumentos, digest_de_head = PLACAS_DE_PF0[caso]
        a, _ = gen.generar_arreglo(**argumentos)
        assert digest_del_arreglo(a) == digest_de_head, f"la placa de PF.0 `{caso}` ya no es la de HEAD"
        b, _ = gen.generar_arreglo(**argumentos, respuestas_netod=None, dosis_meseta_cgy=None)
        assert np.array_equal(a, b), "un `None` explicito es lo mismo que omitir los dos argumentos"

    def test_la_variante_del_generador_pide_sus_dos_argumentos_juntos(self):
        with pytest.raises(ValueError, match="juntas"):
            gen.generar_arreglo(dpi=50, respuestas_netod=RESP)
        with pytest.raises(ValueError, match="juntas"):
            gen.generar_arreglo(dpi=50, dosis_meseta_cgy=DOSIS_MESETA)
