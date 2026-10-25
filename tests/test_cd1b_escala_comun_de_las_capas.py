"""CD.1b (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, tarea CD.1b; P17 de la curva, DA-90; el fisico, 23-10: «Me gustaria que la escala sea la misma en todos los 3 graficos, pues la absoluta completa, para observar
mas facilmente la diferencia de densidad optica entre las capas», y ~13:00, entre las dos lecturas que se le dibujaron, la SEGUNDA: el mayor de las capas NO recortadas por el escaner): LA PESTAÑA «CAPAS» PINTA LAS
TRES CAPAS CON UNA SOLA ESCALA ABSOLUTA.

CAUSA (codigo de HEAD a8d4dee, CD.1): `dibujar_capas` pintaba cada capa de 0 a su tope PROPIO (`CapaEnUnidades.tope`: 1.1 veces su meseta, o su percentil 99.5 sin meseta), asi que la meseta de las tres salia del
mismo color y lo unico que decia cuanto se oscurecio cada una era el numero de su barra. En ML0: la roja de 0 a 2.342, la verde de 0 a 0.797 y la azul de 0 a 0.349.

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale del codigo bajo prueba (la regla de los niveles, los topes, los textos y el mapa `jet` escritos AQUI con numpy, los numeros de ML0 y de la virgen medidos
en los pre-vuelos de Opus, la calibracion del generador independiente de PF.0 y ocho escenas construidas a mano):
  (a) la escala comun de un analisis es el MAYOR de los topes de las capas NO recortadas por el escaner, en la unidad de la base (CD1b-D1, la lectura que eligio el fisico): la capa recortada se pinta contra
      ese tope, satura, y su titulo sigue diciendo «recortada por el escaner». Las capas compiten por niveles (CD1b-D6): primero las no recortadas (con su meseta o con su percentil), si no hay ninguna las
      recortadas, si no hay ninguna las que no tienen ningun pixel mas oscuro que el piso (tope 1: CD1b-D2); una capa en otra unidad (en netOD, la que no tiene piso y se pinta en niveles) no entra y conserva su
      escala de 0 a 255 (CD1b-D3); en valor de pixel las tres ya van de 0 a 255.
  (b) las tres barras tienen los mismos limites (de 0 al tope comun) y el rotulo de CD.1; lo pintado es `jet(valores / tope comun)`; el titulo de cada capa dice su meseta (o por que no la tiene) y la escala comun,
      de 0 a cuanto y de que capas sale (CD1b-D4).
  (c) el dato no cambia: `capa_acondicionada` sigue dando el tope PROPIO de cada capa (es la entrada de la regla comun) y la ventana sigue llamando a `dibujar_capas(figura, resultado)`.
Se prueba en las diez peliculas reales, ML0 con la virgen EPSON179, la sintetica de PF.0 (netOD y valor de pixel), siete casos construidos sobre ML0 (una capa sin piso, sin meseta, recortada, sin ningun pixel mas
oscuro que el piso, la roja SIN recortar que manda, dos recortadas con una sin señal y las tres sin señal), diez escenas construidas de `CapaEnUnidades` (S1 a S10) y la ventana real.

Rojo contra HEAD (a8d4dee): las pruebas de la regla caen por la API que HEAD no tiene (`AttributeError`: `EscalaDeLasCapas`, `escala_de_las_capas`, `tope_en_la_escala_comun`, `texto_en_la_escala_comun`) y las del
dibujo por ASERCION (las tres barras tienen limites distintos). Importa la produccion POR PRUEBA (`_dib()`): cada prueba cae con su razon y no con un error de coleccion. Trampa 2, 9 y 10: como en CD.1 (fixtures
de modulo que se sueltan, la ventana se cierra con `fabrica`, ningun `lru_cache`).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import dataclasses
import inspect
import itertools
import types

import numpy as np
import pytest

import _placa_mensual_sintetica as gen
from _e1_ayudas import _cursor_limpio, analizada, app, archivo_placa, dialogos, fabrica, por_gid, sin_simbolos  # noqa: F401
from test_cd1_capas_en_unidades_absolutas import (  # noqa: F401  (las escenas, el oraculo de CD.1 y su ampliacion de CD.1b; las fixtures de modulo de CD.1)
    ADJETIVO, BASE_OD, BASE_VP, CAPAS, DIBUJO_PY, FACTOR, RAIZ, RECORTADA, REALES, SINT_OD, SINT_VP, TOPE_EN_NIVELES, UNIDAD_OD, UNIDAD_VP, VIRGEN, VP_MINIMO,
    _dib, _pm, escala_comun_esperada, esperado, escena, jet, ml0, pintado, referencia_virgen, sintetica, texto_comun_esperado, titulo_esperado, tope_comun_esperado,
)
from test_d1_guardado_placa_mensual import bd, clics, placa, plantilla  # noqa: F401  (fixtures de D.1: la BD temporal, la sintetica y sus clics)

# las escenas que se DIBUJAN (cada una retiene unos 125 MB y se suelta al terminar su turno): las diez reales, la virgen, la sintetica en las dos bases y siete casos construidos sobre ML0. Los tres ultimos
# (correccion de la ronda 1, R1-AMB-01) existen porque las diez reales tienen la roja recortada y la verde o la azul con señal (nivel 0): sin ellos la ruta del DIBUJO nunca ve una roja que manda, ni una escena
# sin ninguna capa de nivel 0, y la regla pura (S1 a S10) no pasa por `dibujar_capas`.
CONSTRUIDAS_DIBUJADAS = ("construida_sin_piso", "construida_sin_meseta", "construida_solo_el_inplane_recortado", "construida_ningun_pixel_mas_oscuro",
                         "construida_roja_no_recortada_manda", "construida_dos_recortadas_y_una_sin_senal", "construida_ninguna_capa_con_senal")
DIBUJADAS = REALES + (VIRGEN, SINT_OD, SINT_VP) + CONSTRUIDAS_DIBUJADAS
dibujadas = pytest.mark.parametrize("escena", DIBUJADAS, indirect=True)
reales = pytest.mark.parametrize("escena", REALES, indirect=True)

NO_RECORTADAS = "la mayor de las no recortadas"
RECORTADAS = "la mayor de las recortadas por el escáner: no hay capa sin recortar"
SIN_SENAL = "ningún píxel es más oscuro que el piso"
T_SIN_PISO = "valor de píxel de 0 a 255 [nivel]; sin piso no hay densidad óptica: no medible"
T_SIN_SENAL = "la meseta no es más oscura que el piso; de 0 a 1 [1]: ningún píxel es más oscuro que el piso"
T_SIN_MESETA = "la capa no tiene meseta medida; de 0 a 0.700 [1]: el percentil 99.5 de la capa"


def _comun(propio, tope, origen):
    """El texto de una capa pintada con la escala comun, escrito aqui: «<lo suyo>; escala común de 0 a <tope> [1], <de que capas sale>»."""
    return f"{propio}; escala común de 0 a {tope:.3f} [1], {origen}"


# ===================================================================================================== las escenas construidas de CapaEnUnidades (S1 a S10)

def _con_meseta(tope, meseta):
    return _dib().CapaEnUnidades(np.zeros((2, 2), np.float32), tope, UNIDAD_OD, f"de 0 a {tope:.3f} [1]: 1.1 veces su meseta, {meseta:.3f} [1]", meseta, None)


def _recortada(tope):
    return _dib().CapaEnUnidades(np.zeros((2, 2), np.float32), tope, UNIDAD_OD, f"{RECORTADA}; de 0 a {tope:.3f} [1]: el percentil 99.5 de la capa", None, RECORTADA)


def _sin_senal():
    return _dib().CapaEnUnidades(np.zeros((2, 2), np.float32), 1.0, UNIDAD_OD, T_SIN_SENAL, None, "la meseta no es más oscura que el piso")


def _sin_meseta(tope):
    return _dib().CapaEnUnidades(np.zeros((2, 2), np.float32), tope, UNIDAD_OD, T_SIN_MESETA, None, "la capa no tiene meseta medida")


def _sin_piso():
    return _dib().CapaEnUnidades(np.zeros((2, 2), np.float32), 255.0, UNIDAD_VP, T_SIN_PISO, None, "sin piso no hay densidad óptica: no medible")


def _en_niveles(meseta):
    return _dib().CapaEnUnidades(np.zeros((2, 2), np.float32), 255.0, UNIDAD_VP, f"valor de píxel de 0 a 255 [nivel]; piso 170.0 y meseta {meseta:.1f} [nivel]", meseta, None)


# nombre -> (base, {capa: constructor}); mas abajo, lo que la regla debe dar de cada una, escrito a mano
CONSTRUIDAS = {
    "S1": (BASE_OD, {"R": _sin_piso, "G": lambda: _con_meseta(0.9, 0.82), "B": lambda: _con_meseta(0.4, 0.36)}),
    "S2": (BASE_OD, {"R": lambda: _recortada(2.3), "G": lambda: _con_meseta(0.5, 0.45), "B": lambda: _con_meseta(0.9, 0.82)}),
    "S3": (BASE_OD, {"R": _sin_senal, "G": lambda: _con_meseta(0.8, 0.73), "B": lambda: _con_meseta(0.3, 0.27)}),
    "S4": (BASE_VP, {"R": lambda: _en_niveles(20.0), "G": lambda: _en_niveles(32.0), "B": lambda: _en_niveles(39.0)}),
    "S5": (BASE_OD, {"R": lambda: _recortada(2.3), "G": lambda: _recortada(1.9), "B": lambda: _con_meseta(0.4, 0.36)}),
    "S6": (BASE_OD, {"R": lambda: _recortada(2.3), "G": lambda: _recortada(1.9), "B": _sin_senal}),
    "S7": (BASE_OD, {"R": _sin_senal, "G": _sin_senal, "B": _sin_senal}),
    "S8": (BASE_OD, {"R": lambda: _sin_meseta(0.7), "G": lambda: _con_meseta(0.5, 0.45), "B": lambda: _con_meseta(0.3, 0.27)}),
    "S9": (BASE_OD, {"R": lambda: _con_meseta(0.3, 0.27), "G": lambda: _con_meseta(0.5, 0.45), "B": lambda: _con_meseta(0.5, 0.45)}),
    "S10": (BASE_OD, {"R": _sin_piso, "G": _sin_piso, "B": _sin_piso}),
}
# nombre -> ((tope, unidad, capa, origen) de la escala comun o None, {capa: (tope con que se pinta, texto del titulo)})
ESPERADO = {
    "S1": ((0.9, UNIDAD_OD, "G", "no_recortadas"),            # la roja esta en niveles (sin piso): no entra y conserva su escala de 0 a 255 y su texto; la verde (0.9) manda sobre la azul (0.4)
           {"R": (255.0, T_SIN_PISO), "G": (0.9, _comun("meseta 0.820 [1]", 0.9, NO_RECORTADAS)), "B": (0.9, _comun("meseta 0.360 [1]", 0.9, NO_RECORTADAS))}),
    "S2": ((0.9, UNIDAD_OD, "B", "no_recortadas"),            # la roja recortada (2.3) no manda: satura contra el 0.9 de la azul
           {"R": (0.9, _comun(RECORTADA, 0.9, NO_RECORTADAS)), "G": (0.9, _comun("meseta 0.450 [1]", 0.9, NO_RECORTADAS)), "B": (0.9, _comun("meseta 0.820 [1]", 0.9, NO_RECORTADAS))}),
    "S3": ((0.8, UNIDAD_OD, "G", "no_recortadas"),            # la roja sin señal (tope 1, mayor que 0.8) no entra mientras otra capa tenga un tope que salga de su pelicula (CD1b-D2)
           {"R": (0.8, _comun("la meseta no es más oscura que el piso", 0.8, NO_RECORTADAS)), "G": (0.8, _comun("meseta 0.730 [1]", 0.8, NO_RECORTADAS)),
            "B": (0.8, _comun("meseta 0.270 [1]", 0.8, NO_RECORTADAS))}),
    "S4": ((255.0, UNIDAD_VP, "R", "no_recortadas"),          # en valor de pixel las tres ya van de 0 a 255: el titulo es el de CD.1 tal cual
           {"R": (255.0, "valor de píxel de 0 a 255 [nivel]; piso 170.0 y meseta 20.0 [nivel]"), "G": (255.0, "valor de píxel de 0 a 255 [nivel]; piso 170.0 y meseta 32.0 [nivel]"),
            "B": (255.0, "valor de píxel de 0 a 255 [nivel]; piso 170.0 y meseta 39.0 [nivel]")}),
    "S5": ((0.4, UNIDAD_OD, "B", "no_recortadas"),            # una sola capa no recortada: su tope es el comun; las dos recortadas saturan
           {"R": (0.4, _comun(RECORTADA, 0.4, NO_RECORTADAS)), "G": (0.4, _comun(RECORTADA, 0.4, NO_RECORTADAS)), "B": (0.4, _comun("meseta 0.360 [1]", 0.4, NO_RECORTADAS))}),
    "S6": ((2.3, UNIDAD_OD, "R", "recortadas"),               # ninguna no recortada: el mayor de las recortadas, y el titulo lo dice; la azul sin señal se pinta con el comun
           {"R": (2.3, _comun(RECORTADA, 2.3, RECORTADAS)), "G": (2.3, _comun(RECORTADA, 2.3, RECORTADAS)), "B": (2.3, _comun("la meseta no es más oscura que el piso", 2.3, RECORTADAS))}),
    "S7": ((1.0, UNIDAD_OD, "R", "sin_senal"),                # ninguna con señal: el comun es TOPE_SIN_SENAL
           {c: (1.0, _comun("la meseta no es más oscura que el piso", 1.0, SIN_SENAL)) for c in CAPAS}),
    "S8": ((0.7, UNIDAD_OD, "R", "no_recortadas"),            # una capa no recortada SIN meseta (su tope es un percentil) tambien cuenta entre las primeras
           {"R": (0.7, _comun("la capa no tiene meseta medida", 0.7, NO_RECORTADAS)), "G": (0.7, _comun("meseta 0.450 [1]", 0.7, NO_RECORTADAS)),
            "B": (0.7, _comun("meseta 0.270 [1]", 0.7, NO_RECORTADAS))}),
    "S9": ((0.5, UNIDAD_OD, "G", "no_recortadas"),            # con un empate gana la primera de R, G, B
           {"R": (0.5, _comun("meseta 0.270 [1]", 0.5, NO_RECORTADAS)), "G": (0.5, _comun("meseta 0.450 [1]", 0.5, NO_RECORTADAS)), "B": (0.5, _comun("meseta 0.450 [1]", 0.5, NO_RECORTADAS))}),
    "S10": (None,                                             # ninguna capa esta en la unidad de la base: no hay escala comun y cada una conserva la suya
            {c: (255.0, T_SIN_PISO) for c in CAPAS}),
}
ESCENAS_CONSTRUIDAS = tuple(CONSTRUIDAS)
construidas = pytest.mark.parametrize("nombre", ESCENAS_CONSTRUIDAS)


def _armar(nombre):
    base, constructores = CONSTRUIDAS[nombre]
    return types.SimpleNamespace(base=base), {capa: construir() for capa, construir in constructores.items()}


# ===================================================================================================== (a) la regla, con escenas construidas

class TestLaReglaDeLaEscalaComun:
    @construidas
    def test_la_escala_comun_es_el_mayor_de_los_topes_de_las_capas_no_recortadas_en_la_unidad_de_la_base(self, nombre):
        resultado, capas = _armar(nombre)
        escala = _dib().escala_de_las_capas(resultado, capas)
        esperada = ESPERADO[nombre][0]
        if esperada is None:
            assert escala is None, nombre
            return
        tope, unidad, capa, origen = esperada
        assert escala is not None and isinstance(escala, _dib().EscalaDeLasCapas), nombre
        assert escala.tope == pytest.approx(tope, rel=1e-12, abs=0) and escala.unidad == unidad and escala.capa == capa and escala.origen == origen, (nombre, escala)

    @construidas
    def test_cada_capa_se_pinta_con_el_tope_comun_y_una_capa_en_otra_unidad_con_el_suyo(self, nombre):
        resultado, capas = _armar(nombre)
        d = _dib()
        escala = d.escala_de_las_capas(resultado, capas)
        for capa in CAPAS:
            assert d.tope_en_la_escala_comun(capas[capa], escala) == pytest.approx(ESPERADO[nombre][1][capa][0], rel=1e-12, abs=0), (nombre, capa)

    @construidas
    def test_el_titulo_de_cada_capa_dice_su_meseta_y_la_escala_comun_y_de_que_capas_sale(self, nombre):
        resultado, capas = _armar(nombre)
        d = _dib()
        escala = d.escala_de_las_capas(resultado, capas)
        for capa in CAPAS:
            texto = d.texto_en_la_escala_comun(capa, capas[capa], escala)
            assert texto == ESPERADO[nombre][1][capa][1], (nombre, capa, texto)
            assert sin_simbolos(texto) and not texto.endswith("."), (nombre, capa, "sin simbolos de correcto o incorrecto (DA-18) ni punto final")

    def test_una_capa_recortada_dice_que_esta_recortada_y_ninguna_otra_lo_dice(self):
        """El titulo de la roja de S2 sigue diciendo «recortada por el escáner» aunque la escala sea la de la azul; las que no estan recortadas dicen su meseta."""
        resultado, capas = _armar("S2")
        escala = _dib().escala_de_las_capas(resultado, capas)
        textos = {c: _dib().texto_en_la_escala_comun(c, capas[c], escala) for c in CAPAS}
        assert textos["R"].startswith("recortada por el escáner; escala común de 0 a 0.900 [1]")
        assert all("recortada por el escáner;" not in textos[c] for c in ("G", "B")) and all(textos[c].startswith("meseta ") for c in ("G", "B"))

    @construidas
    def test_la_escala_comun_no_depende_del_orden_del_diccionario_y_en_un_empate_gana_la_primera_de_CAPAS(self, nombre):
        """R1-AMB-02: el desempate es «la primera de R, G, B» (docstring de `EscalaDeLasCapas` y pistas §4), sea cual sea el orden en que el llamador arme el diccionario. S9 (G y B empatan en 0.5 sin recortar: gana G)
        y S7 (las tres sin señal empatan en 1: gana R) son los empates; en las demas escenas el orden tampoco cambia nada. Las seis permutaciones de las tres capas."""
        resultado, capas = _armar(nombre)
        esperada = ESPERADO[nombre][0]
        for orden in itertools.permutations(CAPAS):
            escala = _dib().escala_de_las_capas(resultado, {capa: capas[capa] for capa in orden})
            if esperada is None:
                assert escala is None, (nombre, orden)
                continue
            tope, unidad, capa, origen = esperada
            assert escala is not None and (escala.unidad, escala.capa, escala.origen) == (unidad, capa, origen) and escala.tope == pytest.approx(tope, rel=1e-12, abs=0), (nombre, orden, escala)

    def test_la_regla_no_cambia_lo_que_recibe(self):
        """Pura: las capas (y el diccionario) que recibe quedan como estaban."""
        resultado, capas = _armar("S2")
        antes = {c: dataclasses.astuple(capas[c])[1:] for c in CAPAS}
        copia = dict(capas)
        d = _dib()
        escala = d.escala_de_las_capas(resultado, capas)
        for c in CAPAS:
            d.tope_en_la_escala_comun(capas[c], escala)
            d.texto_en_la_escala_comun(c, capas[c], escala)
        assert capas == copia and {c: dataclasses.astuple(capas[c])[1:] for c in CAPAS} == antes


# ===================================================================================================== (b) el dibujo: las tres capas con la misma escala

class TestElDibujoPintaLasTresCapasConLaMismaEscala:
    @dibujadas
    def test_las_tres_barras_tienen_los_mismos_limites_de_cero_al_mayor_de_los_topes_de_las_no_recortadas(self, escena):
        """Cada barra va de 0 al tope comun (el de la oraculo escrito en CD.1 y CD.1b) y dice la unidad de CD.1; la capa en otra unidad (sin piso, en niveles) conserva su barra de 0 a 255."""
        esc = escena.escala()
        assert len(escena.figura.axes) == 6 and [e.get_label() for e in escena.figura.axes[3:]] == ["<colorbar>"] * 3
        for k, capa in enumerate(CAPAS):
            esp = escena.esperado(capa)
            barra = escena.figura.axes[3 + k]
            tope = tope_comun_esperado(esc, esp)
            assert barra.get_xlabel() == esp.unidad, (capa, barra.get_xlabel())
            assert tuple(float(v) for v in barra.get_xlim()) == (0.0, pytest.approx(tope, rel=1e-9)), (capa, barra.get_xlim(), tope)
        en_la_unidad = [tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) for k, capa in enumerate(CAPAS) if escena.esperado(capa).unidad == esc.unidad]
        assert len(set(en_la_unidad)) == 1, f"las barras de las capas en {esc.unidad} tienen los mismos limites: {en_la_unidad}"

    @dibujadas
    def test_lo_pintado_es_el_mapa_jet_de_los_valores_entre_cero_y_el_tope_comun(self, escena):
        """Lo que `dibujar_capas` puso en el eje es `jet(valores / tope comun)` en RGBA uint8, pixel a pixel (la capa en otra unidad, con su tope de 255)."""
        esc = escena.escala()
        for k, capa in enumerate(CAPAS):
            esp = escena.esperado(capa)
            arreglo = pintado(escena.figura, k)
            assert arreglo.dtype == np.uint8 and arreglo.shape == (*esp.valores.shape, 4)
            assert np.array_equal(arreglo, jet(esp.valores / np.float32(tope_comun_esperado(esc, esp)))), f"{capa}: lo pintado no es jet(valores / tope comun)"

    @dibujadas
    def test_el_titulo_de_cada_capa_dice_su_meseta_y_la_escala_comun(self, escena):
        esc = escena.escala()
        for k, capa in enumerate(CAPAS):
            titulo = escena.figura.axes[k].get_title()
            esperado_ = titulo_esperado(capa, texto_comun_esperado(esc, escena.esperado(capa)))
            assert titulo == esperado_, (capa, titulo)
            assert sin_simbolos(titulo) and not titulo.endswith(".") and all(len(renglon) <= 52 for renglon in titulo.split("\n")), (capa, titulo)

    @reales
    def test_la_recortada_satura_contra_la_escala_comun_y_su_titulo_dice_que_esta_recortada(self, escena):
        """La roja de las diez peliculas reales esta recortada por el escaner (su tope propio, hasta el negro del escaner, es mucho mayor que el comun): se pinta contra el tope de la verde o la azul, el
        color de lo que pasa del tope es el extremo del mapa (`jet(1)`), y el titulo sigue diciendo «recortada por el escáner»."""
        esc = escena.escala()
        roja = escena.esperado("R")
        assert roja.motivo == RECORTADA and esc.capa in ("G", "B") and esc.nivel == 0 and roja.tope > 1.5 * esc.tope, "compuerta: la roja esta recortada y su tope propio pasa con creces el comun"
        arreglo = pintado(escena.figura, 0)
        pasa = np.isfinite(roja.valores) & (roja.valores > esc.tope)
        assert pasa.sum() > 0, "compuerta: hay pixeles de la roja por encima del tope comun"
        assert (arreglo[pasa] == jet(np.array([1.0]))[0]).all(), "lo que pasa del tope comun sale con el color del extremo del mapa"
        assert escena.figura.axes[0].get_title().replace("\n", " ").replace(" ", " ").startswith("Capa roja: recortada por el escáner; escala común de 0 a ")
        assert tuple(float(v) for v in escena.figura.axes[3].get_xlim()) == (0.0, pytest.approx(esc.tope, rel=1e-9)), "la barra de la roja va de 0 al tope comun y no a su tope propio"

    @dibujadas
    def test_el_dibujo_y_la_regla_convergen(self, escena):
        """Dos caminos, un resultado: lo que la pestaña dibuja (barras y titulos) es lo que da la regla aplicada a las `capa_acondicionada` del mismo resultado."""
        d = _dib()
        capas = {capa: d.capa_acondicionada(escena.resultado, capa) for capa in CAPAS}
        escala = d.escala_de_las_capas(escena.resultado, capas)
        for k, capa in enumerate(CAPAS):
            assert tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) == (0.0, pytest.approx(d.tope_en_la_escala_comun(capas[capa], escala), rel=1e-9)), capa
            assert escena.figura.axes[k].get_title() == d.titulo_de_la_capa(capa, d.texto_en_la_escala_comun(capa, capas[capa], escala)), capa


# ===================================================================================================== (c) verdad conocida y numeros medidos

class TestLaEscalaComunContraVerdadConocida:
    @pytest.mark.parametrize("escena", ["ML0"], indirect=True)
    def test_en_ML0_la_escala_comun_es_la_de_la_verde_y_los_titulos_son_los_medidos_en_el_pre_vuelo(self, escena):
        """ML0 (piso de las esquinas): la roja, recortada, de 0 a 2.342 por su cuenta; la verde de 0 a 0.797 (meseta 0.724) y la azul de 0 a 0.349 (meseta 0.317). La escala comun es la de la verde: 0.797."""
        for capa, propio in (("R", 2.342), ("G", 0.797), ("B", 0.349)):
            assert _dib().capa_acondicionada(escena.resultado, capa).tope == pytest.approx(propio, abs=1.5e-3), capa
        assert len({tuple(round(float(v), 6) for v in escena.figura.axes[3 + k].get_xlim()) for k in range(3)}) == 1
        for k in range(3):
            assert tuple(escena.figura.axes[3 + k].get_xlim())[0] == 0.0 and tuple(escena.figura.axes[3 + k].get_xlim())[1] == pytest.approx(0.797, abs=1.5e-3), k
        textos = [escena.figura.axes[k].get_title().replace("\n", " ").replace(" ", " ") for k in range(3)]
        assert textos[0] == "Capa roja: recortada por el escáner; escala común de 0 a 0.797 [1], la mayor de las no recortadas"
        assert textos[1] == "Capa verde: meseta 0.724 [1]; escala común de 0 a 0.797 [1], la mayor de las no recortadas"
        assert textos[2] == "Capa azul: meseta 0.317 [1]; escala común de 0 a 0.797 [1], la mayor de las no recortadas"

    @pytest.mark.parametrize("escena", [VIRGEN], indirect=True)
    def test_con_la_pelicula_virgen_la_escala_comun_es_la_de_la_verde_con_su_piso_de_virgen(self, escena):
        """Con el piso de la virgen EPSON179 (R 152.12, G 194.11, B 86.77) los topes propios son 2.483, 0.841 y 0.376: la comun, 0.841."""
        r = escena.resultado
        assert r.piso.modo == "virgen"
        for k in range(3):
            xlim = escena.figura.axes[3 + k].get_xlim()
            assert xlim[0] == 0.0 and xlim[1] == pytest.approx(0.841, abs=1.5e-3), (CAPAS[k], xlim)

    @pytest.mark.parametrize("escena", [SINT_OD], indirect=True)
    def test_en_la_sintetica_la_escala_comun_sale_de_la_calibracion_de_su_generador(self, escena):
        """El generador de PF.0 da el nivel de la meseta de cada capa sin ruido (`gen.CALIB`): el tope propio de G y de B es 1.1 veces log10(piso medido / ese nivel) y la comun es el mayor de los dos; la roja de
        la sintetica esta recortada (su meseta vale 1 nivel) y satura. Verdad que no sale del motor ni del dibujo."""
        r = escena.resultado
        topes = {}
        for capa in ("G", "B"):
            piso = float(r.capas[capa].piso)
            topes[capa] = FACTOR * np.log10(piso / gen.CALIB["meseta_bgr"][gen.INDICE_CAPA[capa]])
        comun = max(topes.values())
        assert _dib().capa_acondicionada(r, "R").motivo == RECORTADA, "compuerta: la roja de la sintetica esta recortada"
        for k in range(3):
            xlim = escena.figura.axes[3 + k].get_xlim()
            assert xlim[0] == 0.0 and xlim[1] == pytest.approx(comun, abs=0.005), (CAPAS[k], xlim, topes)
        assert max(topes, key=topes.get) in ("G", "B")

    @pytest.mark.parametrize("escena", [SINT_VP], indirect=True)
    def test_en_valor_de_pixel_las_tres_capas_van_de_0_a_255_con_el_titulo_de_CD1(self, escena):
        r = escena.resultado
        assert r.base == BASE_VP
        for k, capa in enumerate(CAPAS):
            assert tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) == (0.0, 255.0) and escena.figura.axes[3 + k].get_xlabel() == UNIDAD_VP
            titulo = escena.figura.axes[k].get_title()
            assert titulo == titulo_esperado(capa, escena.esperado(capa).texto), capa
            assert "escala común" not in titulo, "en valor de pixel el titulo es el de CD.1 tal cual"

    @pytest.mark.parametrize("escena", ["construida_sin_piso"], indirect=True)
    def test_en_netod_una_capa_sin_piso_conserva_su_barra_de_0_a_255_y_no_entra_a_la_escala_comun(self, escena):
        """La verde sin piso se pinta en niveles (CD.1): su barra va de 0 a 255 y su titulo es el de CD.1. La roja (recortada) y la azul se pintan contra el tope de la azul, 0.349: la verde no cuenta."""
        barras = [tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) for k in range(3)]
        assert barras[1] == (0.0, 255.0) and escena.figura.axes[4].get_xlabel() == UNIDAD_VP
        assert barras[0] == (0.0, pytest.approx(0.349, abs=1.5e-3)) and barras[2] == (0.0, pytest.approx(0.349, abs=1.5e-3))
        assert "escala común" not in escena.figura.axes[1].get_title() and "sin piso no hay densidad óptica" in escena.figura.axes[1].get_title().replace("\n", " ")
        assert "escala común de 0 a 0.349 [1], la mayor de las no recortadas" in escena.figura.axes[0].get_title().replace("\n", " ").replace(" ", " ")

    @pytest.mark.parametrize("escena", ["construida_ningun_pixel_mas_oscuro"], indirect=True)
    def test_una_capa_sin_ningun_pixel_mas_oscuro_que_el_piso_no_estira_la_escala_comun(self, escena):
        """CD1b-D2: la verde sin señal tiene tope 1 (para que la escala no tenga ancho cero), mayor que el 0.349 de la azul. Mientras otra capa tenga un tope que sale de su pelicula, ese tope 1 no manda: las tres
        barras van de 0 a 0.349 y el titulo de la verde dice la escala comun y que sale de «la mayor de las no recortadas». Por CD1b-D4 el texto propio de una capa en la escala comun es su meseta o su motivo (aqui
        el de la meseta que no se pudo medir): el titulo ya NO dice «ningun pixel es mas oscuro que el piso» (eso lo dice solo `capa_acondicionada(...).texto`, el de CD.1, que no se pinta), asi que no distingue esta
        capa de una con la meseta no mas oscura pero con pixeles mas oscuros que el piso; la ronda 1 de revision (R1-AMB-03) corrigio este docstring, que prometia lo contrario."""
        for k in range(3):
            assert tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) == (0.0, pytest.approx(0.349, abs=1.5e-3)), CAPAS[k]
        assert "escala común de 0 a 0.349 [1], la mayor de las no recortadas" in escena.figura.axes[1].get_title().replace("\n", " ").replace(" ", " ")

    @pytest.mark.parametrize("escena", ["construida_sin_meseta"], indirect=True)
    def test_una_capa_no_recortada_sin_meseta_cuenta_con_el_percentil_de_su_capa(self, escena):
        """CD1b-D6: la verde sin meseta medida tiene como tope el percentil 99.5 de su capa (0.860), no recortada y mayor que el 0.349 de la azul: es la escala comun, y su titulo lo dice."""
        for k in range(3):
            assert tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) == (0.0, pytest.approx(0.860, abs=1.5e-3)), CAPAS[k]
        assert escena.figura.axes[1].get_title().replace("\n", " ").replace(" ", " ").startswith("Capa verde: no medible: perfil crossplane: la zona central de la meseta no está sobre la película; escala común de 0 a 0.860 [1], la mayor de las no recortadas")

    @pytest.mark.parametrize("escena", ["construida_solo_el_inplane_recortado"], indirect=True)
    def test_con_dos_capas_recortadas_la_unica_no_recortada_fija_la_escala(self, escena):
        """La roja y la verde (esta, recortada solo en su inplane) saturan contra la azul: las tres barras van de 0 a 0.349."""
        for k in range(3):
            assert tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) == (0.0, pytest.approx(0.349, abs=1.5e-3)), CAPAS[k]
        assert "Capa verde: recortada por el escáner; escala común de 0 a 0.349 [1], la mayor de las no recortadas" in escena.figura.axes[1].get_title().replace("\n", " ").replace(" ", " ")


# ===================================================================================================== (c-bis) las escenas dibujadas que solo la ruta del dibujo distingue (R1-AMB-01)

def _titulos(escena):
    return [escena.figura.axes[k].get_title().replace("\n", " ").replace("\u00a0", " ") for k in range(3)]


class TestLasEscenasQueSoloElDibujoDistingue:
    """La regla pura (S1 a S10) no pasa por `dibujar_capas`, y las diez peliculas reales tienen la roja recortada con la verde y la azul con señal. Estas tres escenas, construidas sobre ML0, ponen en la ruta del
    DIBUJO lo que ninguna real da: una roja SIN recortar que manda; ninguna capa de nivel 0 con una recortada mayor que otra y una sin señal; y las tres sin señal. Cada una cierra una forma de que el dibujo arme mal
    el diccionario que le pasa a la regla (sin la roja, o sin las recortadas): las baterias M19 y M20."""

    @pytest.mark.parametrize("escena", ["construida_roja_no_recortada_manda"], indirect=True)
    def test_una_roja_sin_recortar_que_manda_fija_la_escala_comun_de_las_tres(self, escena):
        """La roja con la meseta a la decima parte de su piso (netOD 1.0, tope 1.1: sale de la cuenta, no del codigo) no esta recortada y su tope pasa el 0.797 de la verde: la escala de las tres va de 0 a 1.1."""
        for k in range(3):
            assert tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) == (0.0, pytest.approx(1.1, abs=1e-6)), CAPAS[k]
        assert _dib().capa_acondicionada(escena.resultado, "G").tope == pytest.approx(0.797, abs=1.5e-3) and escena.escala().capa == "R" and escena.escala().nivel == 0
        assert _titulos(escena) == ["Capa roja: meseta 1.000 [1]; escala común de 0 a 1.100 [1], la mayor de las no recortadas",
                                    "Capa verde: meseta 0.724 [1]; escala común de 0 a 1.100 [1], la mayor de las no recortadas",
                                    "Capa azul: meseta 0.317 [1]; escala común de 0 a 1.100 [1], la mayor de las no recortadas"]

    @pytest.mark.parametrize("escena", ["construida_dos_recortadas_y_una_sin_senal"], indirect=True)
    def test_sin_ninguna_capa_no_recortada_manda_la_mayor_de_las_recortadas_aunque_haya_una_sin_senal(self, escena):
        """CD1b-D6: la roja (2.342) y la verde (0.860) estan recortadas y la azul no tiene ningun pixel mas oscuro que el piso (tope 1). Las recortadas preceden a la que no tiene señal: el comun es el de la roja, 2.342,
        y no 1; y la roja cuenta (sin ella seria 0.860). El titulo dice que no hay capa sin recortar."""
        for k in range(3):
            assert tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) == (0.0, pytest.approx(2.342, abs=1.5e-3)), CAPAS[k]
        origen = "la mayor de las recortadas por el escáner: no hay capa sin recortar"
        titulos = _titulos(escena)
        assert titulos[0] == f"Capa roja: recortada por el escáner; escala común de 0 a 2.342 [1], {origen}"
        assert titulos[1] == f"Capa verde: recortada por el escáner; escala común de 0 a 2.342 [1], {origen}"
        assert titulos[2] == f"Capa azul: no medible: perfil crossplane: la zona central de la meseta no está sobre la película; escala común de 0 a 2.342 [1], {origen}"
        assert escena.escala().nivel == 1

    @pytest.mark.parametrize("escena", ["construida_ninguna_capa_con_senal"], indirect=True)
    def test_con_las_tres_sin_senal_la_escala_comun_es_de_0_a_1_y_el_titulo_lo_dice(self, escena):
        """CD1b-D6: ningun pixel de ninguna capa es mas oscuro que el piso: el comun es `TOPE_SIN_SENAL` (1) y el origen dice «ningun pixel es mas oscuro que el piso»."""
        for k in range(3):
            assert tuple(float(v) for v in escena.figura.axes[3 + k].get_xlim()) == (0.0, 1.0), CAPAS[k]
        motivo = "no medible: perfil crossplane: la zona central de la meseta no está sobre la película"
        assert _titulos(escena) == [f"Capa {ADJETIVO[capa]}: {motivo}; escala común de 0 a 1.000 [1], ningún píxel es más oscuro que el piso" for capa in CAPAS]
        assert escena.escala().nivel == 2


# ===================================================================================================== la API y lo que no cambia

class TestLaApi:
    def test_escala_de_las_capas_es_una_dataclass_congelada_con_sus_cuatro_campos(self):
        d = _dib()
        assert dataclasses.is_dataclass(d.EscalaDeLasCapas) and d.EscalaDeLasCapas.__dataclass_params__.frozen
        assert [f.name for f in dataclasses.fields(d.EscalaDeLasCapas)] == ["tope", "unidad", "capa", "origen"]
        escala = d.EscalaDeLasCapas(0.5, UNIDAD_OD, "G", "no_recortadas")
        with pytest.raises(dataclasses.FrozenInstanceError):
            escala.tope = 1.0
        assert d.ORIGENES_DE_LA_ESCALA == ("no_recortadas", "recortadas", "sin_senal")

    def test_las_funciones_nuevas_tienen_las_firmas_del_plan_y_las_que_ya_estaban_no_cambian(self):
        d = _dib()
        assert list(inspect.signature(d.escala_de_las_capas).parameters) == ["resultado", "capas"]
        assert list(inspect.signature(d.tope_en_la_escala_comun).parameters) == ["en_unidades", "escala"]
        assert list(inspect.signature(d.texto_en_la_escala_comun).parameters) == ["capa", "en_unidades", "escala"]
        assert list(inspect.signature(d.dibujar_capas).parameters) == ["figura", "resultado"]
        assert list(inspect.signature(d.capa_acondicionada).parameters) == ["resultado", "capa"]
        assert [f.name for f in dataclasses.fields(d.CapaEnUnidades)] == ["valores", "tope", "unidad", "texto", "meseta", "motivo"]

    def test_matplotlib_entra_solo_en_colorear_y_dibujar_capas_y_las_funciones_nuevas_son_puras(self):
        """La regla comun no importa matplotlib ni toca la figura: solo `colorear` y `dibujar_capas` lo importan (exacto, no un subconjunto)."""
        arbol = ast.parse(DIBUJO_PY.read_text(encoding="utf-8"))
        funciones = {f.name: f for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef)}
        con_matplotlib = {nombre for nombre, f in funciones.items() if any(isinstance(n, (ast.Import, ast.ImportFrom)) and "matplotlib" in (getattr(n, "module", None) or ",".join(a.name for a in n.names))
                                                                         for n in ast.walk(f))}
        assert con_matplotlib == {"colorear", "dibujar_capas"}
        for nombre in ("escala_de_las_capas", "tope_en_la_escala_comun", "texto_en_la_escala_comun", "_nivel_de_la_capa", "_sin_senal"):
            assert nombre in funciones, nombre
            assert not any(isinstance(n, ast.Name) and n.id in ("figura", "plt", "Figure") for n in ast.walk(funciones[nombre])), f"{nombre} es pura: no toca la figura"

    def test_el_dibujo_ya_no_pinta_con_el_tope_propio_de_cada_capa(self):
        """La causa: `dibujar_capas` llevaba cada capa a 0-1 con `en_unidades.tope` y su barra iba de 0 a ese tope. Ya no: ni el pintado ni la barra leen el tope propio."""
        arbol = ast.parse(DIBUJO_PY.read_text(encoding="utf-8"))
        dibujar = next(f for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef) and f.name == "dibujar_capas")
        propios = [n.lineno for n in ast.walk(dibujar) if isinstance(n, ast.Attribute) and n.attr == "tope" and isinstance(n.value, ast.Name) and n.value.id == "en_unidades"]
        assert propios == [], f"`dibujar_capas` lee el tope propio de una capa en las lineas {propios}"

    def test_la_ventana_sigue_llamando_a_dibujar_capas_con_la_figura_y_el_resultado(self):
        ventana = (RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "placa_mensual.py").read_text(encoding="utf-8")
        assert ventana.count("dibujar_capas(") == 1 and "dibujo.dibujar_capas(self._fig_capas, resultado)" in ventana


# ===================================================================================================== la ventana real

class TestLaVentana:
    def _comprobar(self, v, r):
        """La pestaña 2 de la ventana es la regla de CD.1b aplicada a su resultado: barras, titulos y lo pintado con la escala comun."""
        figura = v._fig_capas
        esps = {capa: esperado(r, capa) for capa in CAPAS}
        esc = escala_comun_esperada(r, esps)
        assert len(figura.axes) == 6
        for k, capa in enumerate(CAPAS):
            tope = tope_comun_esperado(esc, esps[capa])
            barra = figura.axes[3 + k]
            assert barra.get_xlabel() == esps[capa].unidad and tuple(float(x) for x in barra.get_xlim()) == (0.0, pytest.approx(tope, rel=1e-9)), (capa, barra.get_xlim())
            assert figura.axes[k].get_title() == titulo_esperado(capa, texto_comun_esperado(esc, esps[capa])), capa
            assert np.array_equal(pintado(figura, k), jet(esps[capa].valores / np.float32(tope))), capa
        assert v.nota_pestana2.text() == "", "CD1-D10: la ventana no agrega nota a la pestaña 2"
        return esc

    def test_la_ventana_pinta_la_pestana_de_las_capas_con_la_escala_comun_en_netod(self, fabrica, dialogos, archivo_placa, clics):
        v = fabrica()
        analizada(v, dialogos, archivo_placa, clics)
        r = v._resultado
        assert r.base == BASE_OD
        esc = self._comprobar(v, r)
        limites = {tuple(float(x) for x in v._fig_capas.axes[3 + k].get_xlim()) for k in range(3)}
        assert len(limites) == 1 and esc.unidad == UNIDAD_OD, "las tres barras de la ventana tienen los mismos limites"

    def test_un_analisis_en_valor_de_pixel_se_pinta_en_niveles_de_0_a_255_como_antes(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        monkeypatch.setitem(_pm().VALORES_DE_LA_GEOMETRIA, "base_de_la_medida", BASE_VP)
        v = fabrica()
        analizada(v, dialogos, archivo_placa, clics)
        r = v._resultado
        assert r.base == BASE_VP
        self._comprobar(v, r)
        assert all(tuple(float(x) for x in v._fig_capas.axes[3 + k].get_xlim()) == (0.0, 255.0) for k in range(3))
