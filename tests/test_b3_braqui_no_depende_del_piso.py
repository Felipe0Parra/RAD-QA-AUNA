"""B.3 (PLAN_ANALISIS_PELICULAS_08-10.md): la POSICION INICIAL de braquiterapia mide el desfase SOLO con la mancha y la linea; el piso, el fondo y lo que queda fuera de la ventana de medida no lo mueven.

CAUSA (H11): hoy el motor no usa piso -ni normaliza con el nivel de la pelicula-, pero nada lo fija: una «mejora» que normalizara el perfil con el piso (como hace el motor mensual) lo metería sin que
nada lo viera, y el fisico pidio que el piso nunca sea el vacio tambien aqui: la garantia mas fuerte es que no se use. Esta prueba SOLO agrega pruebas (riesgo NULO): ni el motor, ni el servicio, ni la
pagina cambian. Los modulos auxiliares son `_ventanas_de_medida_braqui.py` (la ventana declarada, pintar, el fondo lejano, comparar y las escenas) y, para la exactitud, `_verdad_braqui.py` y los
generadores de PF.0 (`_placa_braqui_sintetica.py`, independientes del motor).

QUE LEE EL MOTOR (medido, ver `_ventanas_de_medida_braqui.py`): los desfases de gris, R, G y B se miden SOLO dentro de la ventana de `ventana_rotada` (+-20 mm alrededor de la linea y las filas entre los
clics +- 3 mm); el lado del transito se decide en una SEGUNDA ventana, la «larga» (+-52 mm, solo gris), con los pixeles que son pelicula. Por eso son VARIAS pruebas, no una:

  (a) PINTAR FUERA DE LA UNION DE LAS DOS VENTANAS (de blanco, de negro o con el nivel de la pelicula tomado de la propia imagen) no cambia NADA, ni un bit: ni los cuatro perfiles, ni la linea, ni
      el lado ni los contrastes del transito. Lo de fuera se define con la ventana DECLARADA (los parametros y los clics, sin el motor) a 3 px de ella, porque el giro interpola: con margen 0 y 1 el
      borde de la ventana SI ve lo de fuera (control medido, no supuesto), con 2 y 3 no. La pelicula braqui_00 recortada no tiene nada fuera de las ventanas (lo prueba un test aparte): por eso va tambien
      pegada en una pagina del escaner, como EPSON009.
  (b) PINTAR LAS FRANJAS DEL TRANSITO (dentro de la ventana larga, fuera de la corta) no mueve NINGUN desfase ni un bit; el lado del transito queda igual o «sin decidir» (None), NUNCA el contrario; pintar la
      franja del lado SIN banda no toca la banda ni el lado; y pintar la franja de la banda SI llega al transito (control positivo).
  (c) CAMBIAR EL NIVEL DE LA PELICULA donde el motor no puede leer (lejos de la meseta y de la linea, y muy por debajo del umbral de la meseta de cada capa: dentro de la ventana y fuera de ella) no mueve
      NI UN BIT el desfase de ninguna capa -en los dos generadores y en las placas reales-; cambiar ese mismo nivel JUNTO a la mancha y a la linea SI lo mueve (control positivo). Este es el test que ve una
      normalizacion con el minimo, la mediana, un percentil o las esquinas de la ventana (la mutacion del bloque): el piso es una medida del nivel de la pelicula, y aqui el nivel de la pelicula cambia sin
      que cambie nada de lo que el motor mide.
  (d) OTRO NIVEL DE FONDO GLOBAL en las sinteticas (todo el fondo de la pelicula, hombro de la mancha incluido): NO es bit a bit y no puede serlo -el motor lee la orilla de la meseta al umbral, tope - 2.5
      niveles, y esa orilla depende del fondo; medido (cuatro posiciones, seis fondos de -30 a +90 niveles, los dos generadores): el desfase del gris de la MISMA placa se mueve a saltos de 0.25 a 0.5 px (un
      escalon del cruce con el umbral en una imagen de 8 bits) y, en el peor caso, DOS escalones: 1.004 px = 0.0425 mm, contra un techo de 0.05 mm = 1.18 px (un margen de 0.18 px: es una guarda determinista
      sobre estas placas, no una garantia estadistica; obstaculos.md de B.3, 12); el error contra la verdad sigue bajo los techos de B.2 (0.05 mm el gris y 0.10 mm cada capa)
      con cualquier fondo; el lado del transito es el verdadero o «sin decidir» (nunca el contrario): con un fondo tan claro que la pelicula deja de contar como pelicula (umbral de 60) el transito
      puede quedarse sin decidir.
  (e) TRIPWIRE POR AST: ninguna funcion del motor, del servicio ni de la pagina nombra ni importa el piso (`piso_de_pelicula`, `Piso`, la pelicula virgen, sus parametros...; los nombres se derivan de
      `analisisImagenes/pelicula.py`) y el PARAMETROS del motor no tiene ninguna clave de piso.
  (f) las medidas de las tres placas reales son las de PI.1 (sus CLICS_* y CONTROL_*), con una tolerancia de 0.002 px: una normalizacion con piso las mueve (hasta 0.9 px en braqui_00); y el transito
      (el lado, la banda y las dos referencias) de las nueve escenas es el de siempre, con el lado sin pelicula en None: el umbral que separa la pelicula del vacio no se toca.
  (g) LA VENTANA LARGA DEL TRANSITO QUE `analizar` ARMA DE VERDAD mide los 104 mm declarados (+-52 mm): se OBSERVA por dentro, con una espia sobre `ventana_rotada` (`vm.ventanas_que_arma_analizar`), y no se arma
      otra con la misma cuenta. Una holgura de mas o de menos en `analizar` mueve la ventana real aunque casi ninguna salida cambie (el lado, la banda y los contrastes de las nueve escenas no se mueven mas
      de 0.002 niveles; cambian los limites de la banda que se dibuja): sin esto sobrevivian a toda la prueba (R1-LD-03 de la revision de la ronda 1).
  (h) EL MODULO SUELTA SU MEMORIA AL TERMINAR: las escenas (hasta dos paginas enteras, ~160 MB de arreglos cada una) y las placas del criterio (d) se vacian en una fixture de modulo (R1-LD-02).
Cada criterio tiene su prueba con un caso fabricado a mano que lo hace caer (Trampa 8).
"""
import ast
import gc
import re
import types
import weakref
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pytest

import _placa_braqui_sintetica as pb
import _ventanas_de_medida_braqui as vm
import _verdad_braqui as vb
import test_pi1_motor_posicion_inicial as pi1            # los CLICS_* y los CONTROL_* de PI.1: se reutilizan, no se inventan
from analisisImagenes import posicion_inicial_braqui as motor

RAIZ = Path(__file__).resolve().parents[1]
MOTOR_PY = "analisisImagenes/posicion_inicial_braqui.py"
SERVICIO_PY = "services/posicion_inicial_braqui.py"
PAGINA_PY = "ui/paginasControles/PruebasMensuales/posicion_inicial_braqui.py"
PELICULA_PY = "analisisImagenes/pelicula.py"

REALES = ("braqui_00", "EPSON009", "EPSON031")
EMBEBIDAS = ("braqui_00_en_pagina", "EPSON009_en_pagina")
SINTETICAS = ("independiente_en_pagina", "independiente_banda_izquierda_inclinada_en_pagina", "fisico_en_pagina", "fisico_inclinada_en_pagina")
ESCENAS = REALES + EMBEBIDAS + SINTETICAS
CON_PELICULA_FUERA = tuple(n for n in ESCENAS if n != "braqui_00")        # el recorte braqui_00 no tiene nada fuera de las ventanas (test aparte)
ALINEADAS = ("independiente_en_pagina", "fisico_en_pagina")                # la linea es exactamente vertical: la ventana es una traslacion entera de la imagen y no interpola
GIRADAS = tuple(n for n in ESCENAS if n not in ALINEADAS)                  # las reales y las inclinadas 1.5 grados: la ventana gira y el giro (bilineal) mezcla vecinos
LADO_DE_LAS_REALES = "derecha"                                             # medido en las tres: la fuente entra por la derecha de la linea
MINIMO_DE_PIXELES_PINTADOS = 100_000                                       # no vacuidad: una pintura que toca menos que esto no prueba nada
MINIMO_DE_PIXELES_QUE_CAMBIAN = 20_000                                     # ... y tiene que haber cambiado de verdad el valor de los pixeles (EPSON031 es una pagina blanca: pintarla de blanco cambia 46 000)
MINIMO_DEL_BLOQUE_NEGRO = 5_000                                            # el bloque junto a la meseta del control positivo
MINIMO_DEL_FONDO_LEJANO_EN_LA_VENTANA = 20_000                             # pixeles de CADA capa que el cambio del fondo lejano toca DENTRO de la ventana de los desfases


# ============================================================================================================================ las escenas
_CACHE = {}                    # las escenas armadas, por nombre (a lo sumo 2 a la vez)
_PLACAS_DEL_FONDO = {}         # las placas sinteticas del criterio (d), por (modelo, fondo, desfase, semilla)


def _sintetica(nombre):
    if nombre == "independiente_en_pagina":
        placa = pb.generar_independiente(0.5, formato="png", semilla=3, transito=0.95, lado_transito=+1)
    elif nombre == "independiente_banda_izquierda_inclinada_en_pagina":
        placa = pb.generar_independiente(-0.75, formato="png", semilla=4, transito=0.95, lado_transito=-1, inclinacion_deg=1.5)
    elif nombre == "fisico_inclinada_en_pagina":
        placa = pb.generar_fisico(0.5, escenario="inclinada", formato="png", semilla=5)
    else:
        placa = pb.generar_fisico(0.5, escenario="principal", formato="png", semilla=5)
    lado = "derecha" if placa.verdad.lado_transito > 0 else "izquierda"
    base = vm.escena_desde_bytes(nombre, placa.datos, placa.clics, lado)
    base.desfase_verdadero_mm = placa.verdad.desfase_mm
    return vm.en_pagina(base, nombre), placa.verdad


def _real(nombre):
    ruta, clics = {"braqui_00": (pi1.PLACA_REAL, pi1.CLICS_PLACA_REAL), "EPSON009": (pi1.EPSON009, pi1.CLICS_EPSON009), "EPSON031": (pi1.EPSON031, pi1.CLICS_EPSON031)}[nombre]
    return vm.escena_desde_bytes(nombre, ruta.read_bytes(), clics, LADO_DE_LAS_REALES)


def _armar(nombre):
    if nombre in REALES:
        escena = _real(nombre)
    elif nombre in EMBEBIDAS:
        escena = vm.en_pagina(_real(nombre[:-len("_en_pagina")]), nombre)
    else:
        escena = _sintetica(nombre)[0]
    for arreglo in (escena.gris, escena.color, escena.validos):
        arreglo.setflags(write=False)                       # las escenas se comparten entre pruebas: ninguna escribe en ellas (se pinta sobre copias)
    return escena


def construir(nombre):
    """La escena `nombre`, armada una vez y compartida (solo lectura). Se guardan a lo sumo 2 a la vez: una pagina entera pesa ~170 MB."""
    if nombre not in _CACHE:
        while len(_CACHE) >= 2:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[nombre] = _armar(nombre)
    return _CACHE[nombre]


def liberar_las_escenas():
    """Suelta TODO lo que este modulo guarda entre pruebas: las escenas (hasta dos paginas enteras, ~160 MB de arreglos de imagen cada una) y las placas del criterio (d). La fixture de modulo de abajo la llama
    al terminar el modulo: sin ella las dos ultimas escenas quedaban vivas en el proceso, y en la suite repartida las heredaban los archivos siguientes de su reparto (R1-LD-02)."""
    _CACHE.clear()
    _PLACAS_DEL_FONDO.clear()
    gc.collect()


@pytest.fixture(scope="module", autouse=True)
def _suelta_las_escenas_al_terminar_el_modulo():
    yield
    liberar_las_escenas()


@pytest.fixture(scope="module", params=ESCENAS)
def escena(request):
    return construir(request.param)


@pytest.fixture(scope="module", params=CON_PELICULA_FUERA)
def escena_con_pelicula_fuera(request):
    return construir(request.param)


@pytest.fixture(scope="module", params=tuple(n for n in GIRADAS if n in CON_PELICULA_FUERA))
def escena_girada_con_pelicula_fuera(request):
    return construir(request.param)


@pytest.fixture(scope="module", params=ALINEADAS)
def escena_alineada(request):
    return construir(request.param)


def _niveles(nombre_de_la_pintura, escena):
    if nombre_de_la_pintura == "blanco":
        return vm.BLANCO
    if nombre_de_la_pintura == "negro":
        return vm.NEGRO
    return vm.niveles_de_la_pelicula(escena.gris, escena.color, escena.resultado)


PINTURAS = ("blanco", "negro", "pelicula")


def _resumen(difs, n=5):
    return f"{len(difs)} diferencias: " + "; ".join(difs[:n])


# ============================================================================================================================ las escenas son medibles
class TestLasEscenasSonMedibles:
    """No vacuidad de todo lo que sigue: las escenas miden por el camino de verdad (la linea se ubica por su perfil, no contra los clics: DP-145), el gris se mide con filas de sobra, el lado del
    transito esta decidido y es el verdadero, y las sinteticas miden el desfase verdadero."""

    def test_la_linea_se_ubica_por_su_perfil_el_gris_se_mide_con_filas_de_sobra_y_el_lado_es_el_verdadero(self, escena):
        r = escena.resultado
        assert r["mensaje_linea"] == "linea refinada por su perfil", f"{escena.nombre}: {r['mensaje_linea']!r} (con clics lejos de la linea el motor mide contra los clics: DP-145)"
        assert r["perfiles"]["gris"]["estado"] == "ok" and len(r["perfiles"]["gris"]["filas"]) >= 30
        assert r["lado_transito"] == escena.lado_verdadero, f"{escena.nombre}: lado {r['lado_transito']!r}, verdad {escena.lado_verdadero!r}"

    @pytest.mark.parametrize("nombre", SINTETICAS)
    def test_las_sinteticas_miden_el_desfase_verdadero_con_el_gris_y_cada_capa_que_se_mide(self, nombre):
        e = construir(nombre)
        resultado = e.resultado
        for capa in vm.CAPAS:
            assert resultado["perfiles"][capa]["estado"] == "ok", f"{nombre}: la capa {capa} no se mide ({resultado['perfiles'][capa]['estado']})"
            error = abs(motor.resumen(resultado, capa)["desfase_mm"] - e.desfase_verdadero_mm)
            assert error <= vb.TECHO_DEL_ERROR_MM[capa], f"{nombre} {capa}: error {error:.3f} mm > {vb.TECHO_DEL_ERROR_MM[capa]}"


# ============================================================================================================================ (f) la medida de siempre
class TestLaMedidaEsLaDeSiempre:
    """Las tres placas reales miden lo que midieron en PI.1 (sus clics y sus valores de control, reutilizados): con un piso -una normalizacion con el nivel de la pelicula- el numero se mueve. Y el transito
    de las nueve escenas (el lado, la banda y las dos referencias con que se compara) es el que HEAD mide: es lo unico que el motor lee de la pelicula fuera de la mancha."""

    CONTROLES = {"braqui_00": {"gris_px": pi1.CONTROL_G1_PX, "gris_mm": pi1.CONTROL_G1_MM, "U_mm": pi1.CONTROL_G1_U_MM},
                 "EPSON009": dict(pi1.CONTROL_EPSON009), "EPSON031": dict(pi1.CONTROL_EPSON031)}

    @pytest.mark.parametrize("nombre", REALES)
    def test_las_placas_reales_miden_lo_que_midieron_sin_ningun_piso(self, nombre):
        e = construir(nombre)
        r = e.resultado
        control = self.CONTROLES[nombre]
        gris = motor.resumen(r)
        assert gris["desfase_px"] == pytest.approx(control["gris_px"], abs=0.002), nombre
        assert gris["desfase_mm"] == pytest.approx(control["gris_mm"], abs=0.0001), nombre
        assert gris["U_mm"] == pytest.approx(control["U_mm"], abs=0.001), nombre
        assert r["lado_transito"] == LADO_DE_LAS_REALES, nombre
        if nombre == "braqui_00":
            # PI.1 (G1) no fija las capas de braqui_00 con numeros: G y B coinciden con el gris a 0.03 mm y la roja satura hasta el borde de la pelicula y no se mide
            for capa in ("G", "B"):
                assert r["perfiles"][capa]["estado"] == "ok" and abs(r["perfiles"][capa]["desfase_px"] - r["perfiles"]["gris"]["desfase_px"]) * pb.MM_POR_PX < 0.03, capa
            assert r["perfiles"]["R"]["estado"].startswith("no medible")
            derecha = r["contrastes_transito"]["derecha"]
            for clave in ("banda", "arriba", "abajo"):
                assert derecha[clave] == pytest.approx(pi1.CONTROL_G1_TRANSITO[clave], abs=0.05), clave
            return
        fijadas = [c for c in ("R", "G", "B") if f"{c}_px" in control]
        assert fijadas, "no vacuidad: la placa fija el desfase de alguna capa de color"
        for capa in fijadas:
            assert r["perfiles"][capa]["desfase_px"] == pytest.approx(control[f"{capa}_px"], abs=0.002), (nombre, capa)

    # El TRANSITO de siempre en las nueve escenas (medido con el motor de HEAD el 14-10-2026; braqui_00 es ademas el de PI.1): el lado, la mediana de la banda (niveles invertidos de 8 bits) y las de la
    # pelicula de arriba y de abajo con que se compara. El lado SIN banda no tiene pelicula (en una pagina es el vacio del escaner, en un recorte lo que cae fuera de la imagen): su detalle es None.
    # El transito es lo UNICO que el motor lee de la pelicula fuera de la mancha (con `umbral_pelicula` separa la pelicula del vacio): cualquier cambio de ese umbral o de la referencia de la banda mueve
    # estas cifras aunque el lado quede igual (un umbral en 0 deja pasar el blanco de la pagina a las medianas: la banda de la sintetica pasa de 211 a 179 y el lado sin pelicula deja de ser None).
    TRANSITO_DE_SIEMPRE = {
        "braqui_00": ("derecha", 182.28125, 167.53125, 169.12744140625),
        "EPSON009": ("derecha", 158.65625, 145.9296875, 147.0),
        "EPSON031": ("derecha", 182.9375, 167.740234375, 169.8125),
        "braqui_00_en_pagina": ("derecha", 182.9375, 167.84375, 169.6708984375),
        "EPSON009_en_pagina": ("derecha", 158.3310546875, 145.462890625, 146.5625),
        "independiente_en_pagina": ("derecha", 211.0, 138.0, 138.0),
        "independiente_banda_izquierda_inclinada_en_pagina": ("izquierda", 213.0166015625, 137.71875, 137.71875),
        "fisico_en_pagina": ("derecha", 158.0, 146.0, 146.0),
        "fisico_inclinada_en_pagina": ("derecha", 158.853515625, 146.25, 146.3388671875),
    }

    def test_el_transito_de_todas_las_escenas_es_el_de_siempre(self, escena):
        r = escena.resultado
        lado, banda, arriba, abajo = self.TRANSITO_DE_SIEMPRE[escena.nombre]
        assert r["lado_transito"] == lado, f"{escena.nombre}: el lado del transito"
        detalle = r["contrastes_transito"][lado]
        assert detalle["banda"] == pytest.approx(banda, abs=0.05), f"{escena.nombre}: la banda"
        assert detalle["arriba"] == pytest.approx(arriba, abs=0.05), f"{escena.nombre}: la pelicula de arriba"
        assert detalle["abajo"] == pytest.approx(abajo, abs=0.05), f"{escena.nombre}: la pelicula de abajo"
        assert detalle["contraste"] == pytest.approx(min(banda - arriba, banda - abajo), abs=0.1), f"{escena.nombre}: el contraste es la banda menos la mas parecida de sus dos referencias"
        sin_banda = "izquierda" if lado == "derecha" else "derecha"
        assert r["contrastes_transito"][sin_banda] is None, f"{escena.nombre}: el lado {sin_banda} no tiene pelicula (el vacio no es pelicula): su detalle es {r['contrastes_transito'][sin_banda]!r}"


# ============================================================================================================================ la ventana
class TestLaVentanaDeMedidaEsLaDeclarada:
    """La ventana que el motor usa es la que los parametros y los clics declaran (a ~1 px): sin esto, «fuera de la ventana» seria lo que el propio motor dijera."""

    def test_la_ventana_de_los_desfases_mide_40_mm_de_ancho_y_es_la_que_declaran_los_parametros(self, escena):
        r = escena.resultado
        forma = r["imagenes"]["gris"].shape
        declarado = vm.LO_DECLARADO
        escala = 25.4 / declarado.resolucion_dpi
        assert forma[1] == 2 * round(declarado.ventana_mm / escala) + 1, "ancho de la ventana"
        assert forma[1] * escala == pytest.approx(40.0, abs=0.05), "+-20 mm alrededor de la linea"
        largo_de_los_clics = float(np.hypot(*(np.array(escena.clics[1], float) - np.array(escena.clics[0], float))))
        assert abs(forma[0] - (largo_de_los_clics + 2 * round(declarado.margen_filas_mm / escala) + 1)) <= 3, "las filas entre los clics +- 3 mm"
        desviacion = vm.desviacion_de_la_ventana(vm.esquinas_de_la_ventana_real(r["matriz_ventana"], forma), vm.ventana_corta(escena.clics))
        assert desviacion <= 2.0, f"las esquinas de la ventana real estan a {desviacion:.2f} px de las declaradas (se miden ~1.1)"

    def test_la_ventana_larga_del_transito_mide_104_mm_de_ancho_y_es_la_que_declaran_los_parametros(self, escena):
        """La ventana larga que `analizar` arma DE VERDAD: se observa por dentro (`vm.ventanas_que_arma_analizar`, una espia sobre `ventana_rotada`) en vez de armar una con la misma cuenta. Una holgura de mas o
        de menos en `analizar` (`P["transito_hasta_mm"] + 2.0`) mueve la ventana real y esta prueba lo ve, aunque casi ninguna salida cambie (R1-LD-03)."""
        r = escena.resultado
        armadas = vm.ventanas_que_arma_analizar(escena)
        assert len(armadas) >= 2, f"{escena.nombre}: analizar arma {len(armadas)} ventana(s); se esperaban la de los desfases y la larga del transito"
        larga = max(armadas, key=lambda v: v.imagenes["gris"].shape[1])
        assert larga is not armadas[0], f"{escena.nombre}: la ventana mas ancha que arma analizar es la de los desfases: no hay una ventana larga para el transito"
        forma = larga.imagenes["gris"].shape
        escala = 25.4 / vm.LO_DECLARADO.resolucion_dpi
        assert forma[1] == 2 * round(vm.LO_DECLARADO.transito_mm / escala) + 1, f"{escena.nombre}: la ventana larga que arma analizar mide {forma[1] * escala:.2f} mm de ancho"
        assert forma[1] * escala == pytest.approx(104.0, abs=0.05), "+-52 mm alrededor de la linea"
        assert forma[0] == r["imagenes"]["gris"].shape[0], "las dos ventanas comparten las filas"
        desviacion = vm.desviacion_de_la_ventana(vm.esquinas_de_la_ventana_real(larga.matriz, forma), vm.ventana_larga(escena.clics))
        assert desviacion <= 2.0, f"las esquinas de la ventana larga estan a {desviacion:.2f} px de las declaradas"


# ============================================================================================================================ (a) pintar fuera de las dos ventanas
class TestPintarFueraDeLasDosVentanas:
    @pytest.mark.parametrize("pintura", PINTURAS)
    def test_pintar_fuera_de_las_dos_ventanas_no_cambia_nada_ni_un_bit(self, escena_con_pelicula_fuera, pintura):
        e = escena_con_pelicula_fuera
        fuera = vm.fuera_de_las_dos_ventanas(e.clics, e.gris.shape)
        pelicula_pintada = int((fuera & ~vm.marco_del_motor(e.gris.shape)).sum())
        assert pelicula_pintada >= MINIMO_DE_PIXELES_PINTADOS, f"{e.nombre}: solo {pelicula_pintada} px de pelicula fuera de las ventanas (sin el marco): la prueba no probaria nada"
        g2, c2 = vm.pintar(e.gris, e.color, fuera, _niveles(pintura, e))
        assert int(np.count_nonzero(g2 != e.gris)) >= MINIMO_DE_PIXELES_QUE_CAMBIAN, f"{e.nombre}: pintar de {pintura} no cambio el valor de los pixeles"
        difs = vm.diferencias(e.resultado, e.medir(g2, c2))
        assert not difs, f"{e.nombre} pintado de {pintura} fuera de las dos ventanas: {_resumen(difs)}"

    def test_las_escenas_giradas_y_las_alineadas_son_las_que_el_nombre_dice(self):
        """La linea exactamente vertical (angulo 0) deja la ventana como una traslacion entera de la imagen: no interpola. Las demas giran (de -0.96 a +89.8 grados) y el giro es bilineal."""
        for nombre in ESCENAS:
            angulo = construir(nombre).resultado["angulo"]
            alineada = abs(angulo) < 1e-9
            assert alineada == (nombre in ALINEADAS), f"{nombre}: angulo {angulo}"
        assert set(GIRADAS) | set(ALINEADAS) == set(ESCENAS) and not set(GIRADAS) & set(ALINEADAS)

    @pytest.mark.parametrize("margen", [0, 1])
    def test_sin_margen_el_borde_de_la_ventana_girada_si_ve_lo_de_fuera(self, escena_girada_con_pelicula_fuera, margen):
        """El control del margen (medido, no supuesto): el giro interpola, y con la mascara de «fuera» pegada a la ventana (0 o 1 px de margen) los pixeles del borde de la ventana cambian."""
        e = escena_girada_con_pelicula_fuera
        fuera = vm.fuera_de_las_dos_ventanas(e.clics, e.gris.shape, margen)
        g2, c2 = vm.pintar(e.gris, e.color, fuera, vm.NEGRO)
        difs = vm.diferencias(e.resultado, e.medir(g2, c2))
        assert difs, f"{e.nombre}: con {margen} px de margen pintar de negro lo de fuera NO cambio la ventana: el margen de {vm.MARGEN_PX} px ya no hace falta, o la comparacion es ciega"

    @pytest.mark.parametrize("margen", [0, 1])
    def test_en_una_ventana_alineada_con_los_pixeles_pintar_pegado_a_la_ventana_no_cambia_nada(self, escena_alineada, margen):
        """La contraparte: con la linea exactamente vertical la ventana es una copia de la imagen (sin interpolar) y no ve lo de fuera ni siquiera con margen 0."""
        e = escena_alineada
        fuera = vm.fuera_de_las_dos_ventanas(e.clics, e.gris.shape, margen)
        g2, c2 = vm.pintar(e.gris, e.color, fuera, vm.NEGRO)
        difs = vm.diferencias(e.resultado, e.medir(g2, c2))
        assert not difs, f"{e.nombre}: {_resumen(difs)}"

    @pytest.mark.parametrize("margen", [2, 3])
    def test_con_2_px_de_margen_o_mas_el_borde_ya_no_ve_lo_de_fuera(self, escena_con_pelicula_fuera, margen):
        e = escena_con_pelicula_fuera
        fuera = vm.fuera_de_las_dos_ventanas(e.clics, e.gris.shape, margen)
        g2, c2 = vm.pintar(e.gris, e.color, fuera, vm.NEGRO)
        difs = vm.diferencias(e.resultado, e.medir(g2, c2))
        assert not difs, f"{e.nombre}: con {margen} px de margen pintar de negro lo de fuera cambia lo que el motor mide: {_resumen(difs)}"

    def test_el_recorte_braqui_00_no_tiene_pelicula_fuera_de_las_ventanas(self):
        """Por eso (a) no lo incluye recortado: la ventana larga (+-52 mm) cubre todo el recorte salvo el marco de 25 px que el motor ya pone en cero. Va pegado en una pagina (`braqui_00_en_pagina`)."""
        e = construir("braqui_00")
        fuera = vm.fuera_de_las_dos_ventanas(e.clics, e.gris.shape)
        assert int((fuera & ~vm.marco_del_motor(e.gris.shape)).sum()) == 0
        pagina = construir("braqui_00_en_pagina")
        assert int((vm.fuera_de_las_dos_ventanas(pagina.clics, pagina.gris.shape)).sum()) > 30_000_000

    def test_pintar_junto_a_la_meseta_si_mueve_el_desfase(self, escena_con_pelicula_fuera):
        """Control positivo: un bloque NEGRO pegado a la meseta, DENTRO de la ventana, cambia el resultado (no es que la comparacion no pueda ver diferencias)."""
        e = escena_con_pelicula_fuera
        r = e.resultado
        ventana = r["imagenes"]["gris"]
        medidas = r["perfiles"]["gris"]
        fin = int(medidas["m"]["fin"][medidas["filas"]].max())
        bloque = np.zeros(ventana.shape, np.uint8)
        bloque[int(medidas["filas"].min()):int(medidas["filas"].max()) + 1, fin + 25:fin + 25 + 400] = 1
        sobre_la_original = cv2.warpAffine(bloque, np.asarray(r["matriz_ventana"], np.float64), (e.gris.shape[1], e.gris.shape[0]),
                                           flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0
        assert int(sobre_la_original.sum()) >= MINIMO_DEL_BLOQUE_NEGRO
        g2, c2 = vm.pintar(e.gris, e.color, sobre_la_original, vm.NEGRO)
        difs = vm.diferencias(vm.lo_medido_de_los_desfases(r, motor), vm.lo_medido_de_los_desfases(e.medir(g2, c2), motor))
        assert difs, f"{e.nombre}: un bloque negro junto a la meseta no cambio ningun desfase"


# ============================================================================================================================ (b) pintar las franjas del transito
LADOS_CON_FRANJA = {"braqui_00": ("derecha",), "EPSON009": ("derecha",)}        # los recortes terminan a la izquierda de la ventana corta: solo tienen la franja derecha
LADOS_DE_UNA_PAGINA = ("izquierda", "derecha")


def _lados_con_franja(nombre):
    return LADOS_CON_FRANJA.get(nombre, LADOS_DE_UNA_PAGINA)


class TestPintarLasFranjasDelTransito:
    @pytest.mark.parametrize("pintura", PINTURAS)
    def test_pintar_las_franjas_no_mueve_ningun_desfase_ni_un_bit(self, escena, pintura):
        e = escena
        r = e.resultado
        marco = vm.marco_del_motor(e.gris.shape)
        franjas = vm.franjas_del_transito(e.clics, e.gris.shape, r["matriz_ventana"])
        con_pixeles = tuple(lado for lado in vm.LADOS if (franjas[lado] & ~marco).sum() >= MINIMO_DE_PIXELES_PINTADOS)
        assert con_pixeles == _lados_con_franja(e.nombre), f"{e.nombre}: tiene franja (>= {MINIMO_DE_PIXELES_PINTADOS} px) en {con_pixeles}, se esperaba {_lados_con_franja(e.nombre)}"
        niveles = _niveles(pintura, e)
        fallos = []
        for lado in ("ambas",) + con_pixeles:
            g2, c2 = vm.pintar(e.gris, e.color, franjas[lado], niveles)
            difs = vm.diferencias(r, e.medir(g2, c2), ignorar=("lado_transito", "contrastes_transito"))
            if difs:
                fallos.append(f"franja {lado}: {_resumen(difs, 3)}")
        assert not fallos, f"{e.nombre} con las franjas pintadas de {pintura}: " + " | ".join(fallos)

    @pytest.mark.parametrize("pintura", PINTURAS)
    def test_pintar_las_franjas_deja_el_lado_del_transito_igual_o_sin_decidir_nunca_el_contrario(self, escena, pintura):
        e = escena
        r = e.resultado
        base = r["lado_transito"]
        assert base == e.lado_verdadero, f"{e.nombre}: la placa sin tocar dice {base!r} y la verdad es {e.lado_verdadero!r}"
        franjas = vm.franjas_del_transito(e.clics, e.gris.shape, r["matriz_ventana"])
        niveles = _niveles(pintura, e)
        fallos = []
        for lado in ("ambas",) + _lados_con_franja(e.nombre):
            g2, c2 = vm.pintar(e.gris, e.color, franjas[lado], niveles)
            fallos += [f"franja {lado}: {f}" for f in vm.fallos_del_lado(base, e.medir(g2, c2)["lado_transito"])]
        assert not fallos, f"{e.nombre} pintado de {pintura}: " + " | ".join(fallos)

    @pytest.mark.parametrize("pintura", PINTURAS)
    def test_pintar_la_franja_del_lado_sin_banda_no_toca_la_banda_ni_el_lado(self, escena, pintura):
        """Cada lado lee solo SUS columnas: la franja del lado sin banda pintada no cambia el lado ni, bit a bit, el detalle de la banda (banda, arriba, abajo, contraste y sus limites)."""
        e = escena
        r = e.resultado
        base = r["lado_transito"]
        opuesto = "izquierda" if base == "derecha" else "derecha"
        if opuesto not in _lados_con_franja(e.nombre):
            assert e.nombre in LADOS_CON_FRANJA and opuesto == "izquierda", f"{e.nombre}: no tiene franja del lado {opuesto} y no es un recorte"
            return
        franjas = vm.franjas_del_transito(e.clics, e.gris.shape, r["matriz_ventana"])
        assert (franjas[opuesto] & ~vm.marco_del_motor(e.gris.shape)).sum() >= MINIMO_DE_PIXELES_PINTADOS
        g2, c2 = vm.pintar(e.gris, e.color, franjas[opuesto], _niveles(pintura, e))
        r1 = e.medir(g2, c2)
        assert r1["lado_transito"] == base, f"{e.nombre}: pintar la franja {opuesto} (sin banda) cambio el lado {base!r} a {r1['lado_transito']!r}"
        difs = vm.diferencias(r["contrastes_transito"][base], r1["contrastes_transito"][base])
        assert not difs, f"{e.nombre}: pintar la franja {opuesto} cambio la banda de {base}: {_resumen(difs)}"

    def test_pintar_la_franja_de_la_banda_si_llega_al_transito(self, escena):
        """Control positivo: la franja de la banda pintada de negro SI cambia el detalle del transito (la pintura llega a donde el transito mira)."""
        e = escena
        r = e.resultado
        base = r["lado_transito"]
        franjas = vm.franjas_del_transito(e.clics, e.gris.shape, r["matriz_ventana"])
        assert (franjas[base] & ~vm.marco_del_motor(e.gris.shape)).sum() >= MINIMO_DE_PIXELES_PINTADOS
        g2, c2 = vm.pintar(e.gris, e.color, franjas[base], vm.NEGRO)
        r1 = e.medir(g2, c2)
        assert vm.diferencias(r["contrastes_transito"][base], r1["contrastes_transito"][base]), f"{e.nombre}: la franja de la banda pintada de negro no cambio el detalle del transito"
        assert r1["contrastes_transito"][base] is None or r1["contrastes_transito"][base]["contraste"] < r["contrastes_transito"][base]["contraste"]


# ============================================================================================================================ (c) el nivel de la pelicula lejos de la mancha
CAMBIOS_DEL_FONDO = {"oscurece_60": ("desplazar", 60.0), "aclara_60": ("desplazar", -60.0), "plano_blanco": ("plano", 0.0),
                     "plano_medio": ("plano", 100.0), "plano_oscuro": ("plano", 200.0)}


class TestCambiarElNivelDeLaPeliculaLejosDeLaMancha:
    @pytest.mark.parametrize("cambio", sorted(CAMBIOS_DEL_FONDO))
    def test_cambiar_el_nivel_de_la_pelicula_lejos_de_la_mancha_no_mueve_el_desfase_de_ninguna_capa_ni_un_bit(self, escena, cambio):
        e = escena
        r = e.resultado
        modo, valor = CAMBIOS_DEL_FONDO[cambio]
        protegida = vm.zona_protegida(r, e.gris.shape)
        ventana = vm.mascara_dentro(vm.ventana_corta(e.clics), e.gris.shape, 0.0)
        g2, c2, cambiados, en_la_ventana = vm.cambiar_el_fondo_lejano(e.gris, e.color, r, protegida, modo, valor, ventana)
        for capa in vm.CAPAS:
            assert en_la_ventana[capa] >= MINIMO_DEL_FONDO_LEJANO_EN_LA_VENTANA, f"{e.nombre}: el cambio solo toca {en_la_ventana[capa]} px de la capa {capa} dentro de la ventana de los desfases"
        assert cambiados["gris"] >= 300_000
        assert int(np.count_nonzero(g2 != e.gris)) >= MINIMO_DE_PIXELES_QUE_CAMBIAN, f"{e.nombre}: el cambio {cambio} no cambio el valor de los pixeles"
        r1 = e.medir(g2, c2)
        difs = vm.diferencias(vm.lo_medido_de_los_desfases(r, motor), vm.lo_medido_de_los_desfases(r1, motor))
        assert not difs, f"{e.nombre} con la pelicula lejana cambiada ({cambio}): {_resumen(difs)}"
        assert vm.fallos_del_lado(r["lado_transito"], r1["lado_transito"]) == [], f"{e.nombre}: el lado del transito con la pelicula lejana cambiada ({cambio})"

    def test_cambiar_el_nivel_de_la_pelicula_junto_a_la_mancha_y_a_la_linea_si_mueve_el_desfase(self, escena):
        """Control positivo: el MISMO cambio, hecho solo donde el motor lee (la caja de la meseta y la franja de la linea), cambia lo medido."""
        e = escena
        r = e.resultado
        protegida = vm.zona_protegida(r, e.gris.shape)
        g2, c2, _, _ = vm.cambiar_el_fondo_lejano(e.gris, e.color, r, ~protegida, "plano", 0.0)
        difs = vm.diferencias(vm.lo_medido_de_los_desfases(r, motor), vm.lo_medido_de_los_desfases(e.medir(g2, c2), motor))
        assert difs, f"{e.nombre}: cambiar la pelicula junto a la mancha y a la linea no movio nada: el cambio del fondo lejano no distingue lo que el motor lee"
        r1 = e.medir(g2, c2)
        assert any(r1["perfiles"][c]["desfase_px"] != r["perfiles"][c]["desfase_px"] for c in vm.CAPAS if r["perfiles"][c]["estado"] == "ok" and r1["perfiles"][c]["estado"] == "ok"), \
            "ningun desfase cambio (solo cambio la linea)"


# ============================================================================================================================ (d) otro fondo global en las sinteticas
FONDOS_GLOBALES = (-30, -15, 0, 20, 50, 90)                 # niveles que se suman al fondo (B, G, R) de la pelicula sin dosis
POSICIONES_DEL_FONDO = ((-1.5, 11), (0.5, 12), (2.0, 13), (-0.25, 14))      # (desfase mm, semilla)


def _fondo_con(delta):
    return tuple(float(np.clip(x + delta, 5, 250)) for x in pb.FONDO_EPSON009)


def _placa_con_otro_fondo(modelo, delta, desfase, semilla):
    """La placa de `modelo` con el fondo de la pelicula sin dosis corrido `delta` niveles (el generador fisico lleva el fondo en una constante del modulo: se parcha solo mientras genera). Determinista:
    se genera una vez y se comparte (solo lectura)."""
    clave = (modelo, delta, desfase, semilla)
    if clave not in _PLACAS_DEL_FONDO:
        if modelo == "independiente":
            _PLACAS_DEL_FONDO[clave] = pb.generar_independiente(desfase, formato="png", semilla=semilla, fondo=_fondo_con(delta), transito=0.95, lado_transito=+1)
        else:
            with mock.patch.object(pb, "FONDO_BGR", _fondo_con(delta)):
                _PLACAS_DEL_FONDO[clave] = pb.generar_fisico(desfase, escenario="principal", formato="png", semilla=semilla)
    return _PLACAS_DEL_FONDO[clave]


class TestOtroNivelDeFondoGlobalEnLaSintetica:
    @pytest.mark.parametrize("modelo", ["independiente", "fisico"])
    def test_con_otro_nivel_de_fondo_el_error_contra_la_verdad_sigue_bajo_los_techos_de_b2(self, modelo):
        """El fondo de la pelicula (todo, hombro incluido) sube y baja y el desfase de cada capa sigue siendo el verdadero: gris <= 0.05 mm y cada capa <= 0.10 mm (o dice por que no se mide)."""
        casos = {delta: [vb.caso_de(f"{modelo}/fondo{delta:+d}/d={d:+.2f}", modelo, d, _placa_con_otro_fondo(modelo, delta, d, s)) for d, s in POSICIONES_DEL_FONDO] for delta in FONDOS_GLOBALES}
        fallos = []
        for delta, c in casos.items():
            fallos += [f"fondo {delta:+d}: {f}" for f in vb.fallos_de_error_maximo(c, techo=vb.TECHO_DEL_ERROR_MM["gris"], capas=("gris",), minimo_medidas=len(c))]
            fallos += [f"fondo {delta:+d}: {f}" for f in vb.fallos_de_error_maximo(c, techo=vb.TECHO_DEL_ERROR_MM["R"], capas=("R", "G"), admite_no_medible=True, minimo_medidas=1)]
            fallos += [f"fondo {delta:+d}: {f}" for f in vb.fallos_de_error_maximo(c, techo=vb.TECHO_DEL_ERROR_MM["B"], capas=("B",), admite_no_medible=True, minimo_medidas=0)]
        assert not fallos, "\n".join(fallos)

    @pytest.mark.parametrize("modelo", ["independiente", "fisico"])
    def test_con_otro_nivel_de_fondo_el_desfase_del_gris_se_mueve_menos_que_el_techo_de_exactitud(self, modelo):
        """No es bit a bit (el motor lee la orilla de la meseta al umbral, tope - 2.5 niveles, y esa orilla depende del fondo; el cruce se mueve a saltos de medio pixel en una imagen de 8 bits): el
        desfase del gris de la MISMA placa con otro fondo, de 30 niveles mas oscuro a 90 mas claro, cambia a lo sumo lo que el techo de exactitud del gris permite (0.05 mm; medido: 0.043 mm)."""
        peor = 0.0
        for d, s in POSICIONES_DEL_FONDO:
            medidos = [vb.medir(_placa_con_otro_fondo(modelo, delta, d, s)).medidas["gris"].mm for delta in FONDOS_GLOBALES]
            assert None not in medidos, f"{modelo} d={d}: el gris no se mide con algun fondo"
            peor = max(peor, (max(medidos) - min(medidos)) / pb.MM_POR_PX)
        assert peor * pb.MM_POR_PX <= vb.TECHO_DEL_ERROR_MM["gris"], f"{modelo}: el desfase del gris se movio {peor:.3f} px = {peor * pb.MM_POR_PX:.4f} mm entre fondos (techo {vb.TECHO_DEL_ERROR_MM['gris']} mm)"

    @pytest.mark.parametrize("modelo", ["independiente", "fisico"])
    def test_con_otro_nivel_de_fondo_el_lado_del_transito_es_el_verdadero_o_sin_decidir_nunca_el_contrario(self, modelo):
        decididos = 0
        for delta in FONDOS_GLOBALES:
            placa = _placa_con_otro_fondo(modelo, delta, 0.5, 12)
            esperado = "derecha" if placa.verdad.lado_transito > 0 else "izquierda"
            lado = vb.medir(placa).lado_transito
            assert vm.fallos_del_lado(esperado, lado) == [], f"{modelo} fondo {delta:+d}"
            decididos += lado is not None
        assert decididos >= 4, f"{modelo}: el lado se decidio con solo {decididos} de {len(FONDOS_GLOBALES)} fondos (no vacuidad)"


# ============================================================================================================================ (h) el modulo suelta su memoria al terminar
class _Pesada:
    """Un objeto cualquiera que se vigila con una referencia debil: hace de escena o de placa."""


def _es_fixture_de_modulo_autouse(funcion):
    """True si `funcion` (un `ast.FunctionDef`) esta decorada con `@pytest.fixture(scope="module", autouse=True)`: la que corre sola al cerrar el modulo."""
    for d in funcion.decorator_list:
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "fixture" and isinstance(d.func.value, ast.Name) and d.func.value.id == "pytest":
            claves = {k.arg: k.value for k in d.keywords}
            return all(isinstance(claves.get(c), ast.Constant) and claves[c].value == v for c, v in (("scope", "module"), ("autouse", True)))
    return False


def _llama_a_liberar_al_terminar(funcion):
    """True si el cuerpo de `funcion` tiene UN `yield` y, DESPUES de el (lo que corre al cerrar el modulo), una llamada a `liberar_las_escenas()`."""
    cuerpo = funcion.body
    yields = [i for i, s in enumerate(cuerpo) if isinstance(s, ast.Expr) and isinstance(s.value, ast.Yield)]
    if len(yields) != 1:
        return False
    return any(isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Name) and s.value.func.id == "liberar_las_escenas" for s in cuerpo[yields[0] + 1:])


def _fixtures_que_liberan(texto):
    return [f.name for f in ast.parse(texto).body if isinstance(f, ast.FunctionDef) and _es_fixture_de_modulo_autouse(f) and _llama_a_liberar_al_terminar(f)]


class TestElModuloSueltaSuMemoria:
    def test_liberar_las_escenas_vacia_las_dos_caches_y_suelta_lo_que_guardaban(self, monkeypatch):
        escenas, placas = {}, {}
        monkeypatch.setitem(globals(), "_CACHE", escenas)                    # las caches de verdad no se tocan: otras pruebas del modulo las estan usando
        monkeypatch.setitem(globals(), "_PLACAS_DEL_FONDO", placas)
        escena, placa = _Pesada(), _Pesada()
        escenas["pagina"], placas[("independiente", 0, 0.5, 12)] = escena, placa
        vigiladas = (weakref.ref(escena), weakref.ref(placa))
        del escena, placa
        liberar_las_escenas()
        assert not escenas, "la cache de escenas sigue con escenas"
        assert not placas, "la cache de placas del fondo sigue con placas"
        assert all(v() is None for v in vigiladas), "alguien mas retiene la escena o la placa: no se soltaron de verdad"

    def test_hay_una_fixture_de_modulo_autouse_que_llama_a_liberar_las_escenas_al_terminar_el_modulo(self):
        liberan = _fixtures_que_liberan(Path(__file__).read_text(encoding="utf-8"))
        assert len(liberan) == 1, f"debe haber exactamente UNA fixture de modulo autouse que llame a liberar_las_escenas() despues de su yield; hay {liberan}"

    def test_el_detector_de_la_fixture_distingue_la_que_libera_de_las_que_no(self):
        def fuente(decorador, cuerpo):
            return f"@pytest.fixture({decorador})\ndef f():\n" + "".join(f"    {linea}\n" for linea in cuerpo)
        modulo_autouse = "scope='module', autouse=True"
        casos = {
            "libera al terminar": (fuente(modulo_autouse, ["yield", "liberar_las_escenas()"]), True),
            "libera ANTES del yield": (fuente(modulo_autouse, ["liberar_las_escenas()", "yield"]), False),
            "no libera": (fuente(modulo_autouse, ["yield", "pass"]), False),
            "sin autouse": (fuente("scope='module'", ["yield", "liberar_las_escenas()"]), False),
            "de alcance de funcion": (fuente("scope='function', autouse=True", ["yield", "liberar_las_escenas()"]), False),
            "dos yield": (fuente(modulo_autouse, ["yield", "liberar_las_escenas()", "yield"]), False),
        }
        for nombre, (texto, esperado) in casos.items():
            assert bool(_fixtures_que_liberan(texto)) == esperado, nombre


# ============================================================================================================================ (e) el tripwire por AST: el piso no entra en el braqui
PATRON_DE_LO_QUE_HABLA_DEL_PISO = re.compile(r"piso|virgen|esquina|respaldo|modo|comparacion", re.IGNORECASE)
NOMBRES_DEL_PLAN = ("piso_de_pelicula", "piso_de_pelicula_virgen", "Piso", "ReferenciaVirgen", "guardar_referencia_virgen", "leer_referencia_virgen", "PARAMETROS_DEL_PISO", "VALORES_DEL_PISO")
ARCHIVOS_SIN_PISO = {MOTOR_PY: ("el motor", 15), SERVICIO_PY: ("el servicio", 12), PAGINA_PY: ("la pagina", 40)}      # {ruta: (que es, minimo de funciones)}
MODULO_DE_LA_PELICULA = "analisisImagenes.pelicula"


def _leer_fuentes():
    fuentes = {}
    for ruta in (PELICULA_PY, *ARCHIVOS_SIN_PISO):
        texto = (RAIZ / ruta).read_text(encoding="utf-8")
        fuentes[ruta] = (texto, ast.parse(texto, ruta))
    return fuentes


def _fuente(texto, ruta="<sintetico>.py"):
    return {ruta: (texto, ast.parse(texto))}


def nombres_definidos(arbol):
    """Los nombres de nivel de modulo de un arbol: funciones, clases y asignaciones."""
    nombres = set()
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nombres.add(n.name)
        elif isinstance(n, ast.Assign):
            nombres |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            nombres.add(n.target.id)
    return nombres


def nombres_del_piso(fuentes):
    """DERIVADO del arbol: lo que `pelicula.py` define a nivel de modulo y habla del piso, de la pelicula virgen, de las esquinas, de los respaldos, de los modos o de la comparacion. El lector
    (`leer_pelicula`, `Pelicula`, `clase_resolucion`, `escala_mm`, `CAPAS`...) no entra: el braqui lo usa."""
    return {n for n in nombres_definidos(fuentes[PELICULA_PY][1]) if PATRON_DE_LO_QUE_HABLA_DEL_PISO.search(n)}


def _funcion_contenedora(arbol):
    contenedora = {id(arbol): None}

    def visitar(nodo, funcion):
        for hijo in ast.iter_child_nodes(nodo):
            propia = hijo.name if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef)) else funcion
            contenedora[id(hijo)] = propia
            visitar(hijo, propia)
    visitar(arbol, None)
    return contenedora


def usos_del_piso(fuentes, ruta, nombres):
    """[(que, funcion, linea)] de todo lo que en `ruta` nombra o importa el piso: un nombre, un atributo (`pelicula.piso_de_pelicula`), un import (con nombre o con `*`) o una cadena que es el
    nombre (`getattr(pelicula, "piso_de_pelicula")`). Cada uso dice en que funcion esta."""
    _, arbol = fuentes[ruta]
    contenedora = _funcion_contenedora(arbol)
    usos = []
    for n in ast.walk(arbol):
        funcion = contenedora.get(id(n))
        if isinstance(n, ast.Name) and n.id in nombres:
            usos.append((f"nombre {n.id}", funcion, n.lineno))
        elif isinstance(n, ast.Attribute) and n.attr in nombres:
            usos.append((f"atributo .{n.attr}", funcion, n.lineno))
        elif isinstance(n, ast.ImportFrom):
            for alias in n.names:
                if alias.name in nombres or (alias.name == "*" and (n.module or "").endswith("pelicula")):
                    usos.append((f"import {alias.name} de {n.module}", funcion, n.lineno))
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in nombres:
            usos.append((f"cadena {n.value!r}", funcion, n.lineno))
    return sorted(usos, key=lambda u: (u[2], u[0]))


def importaciones_de_pelicula(fuentes, ruta):
    """Los nombres que `ruta` importa de `analisisImagenes.pelicula` (para la no vacuidad: la guarda tiene que VER los imports del lector)."""
    _, arbol = fuentes[ruta]
    return sorted({a.name for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module == MODULO_DE_LA_PELICULA for a in n.names})


def claves_de_piso(fuentes_vivas=None):
    """Las claves de parametros que son del piso o de la pelicula virgen, DERIVADAS de los diccionarios de `pelicula.py` (menos las de la escala, que el piso comparte con el motor)."""
    from analisisImagenes import pelicula
    claves = set(pelicula.VALORES_DEL_PISO) | set(pelicula.PARAMETROS_DEL_PISO) | set(pelicula.VALORES_DE_LA_VIRGEN) | set(pelicula.PARAMETROS_DE_LA_VIRGEN)
    return claves - set(pelicula.CLAVES_DE_LA_ESCALA)


def claves_de_piso_en(parametros, claves):
    return sorted(k for k in parametros if k in claves or re.search(r"piso|virgen", k, re.IGNORECASE))


@pytest.fixture(scope="module")
def fuentes():
    return _leer_fuentes()


class TestElPisoNoEntraEnElMotorNiEnElServicioNiEnLaPagina:
    @pytest.mark.parametrize("ruta", sorted(ARCHIVOS_SIN_PISO))
    def test_ninguna_funcion_nombra_ni_importa_el_piso(self, fuentes, ruta):
        usos = usos_del_piso(fuentes, ruta, nombres_del_piso(fuentes))
        assert not usos, f"{ARCHIVOS_SIN_PISO[ruta][0]} ({ruta}) usa el piso: {usos}"

    def test_el_parametros_del_motor_no_tiene_ninguna_clave_de_piso(self):
        assert claves_de_piso_en(motor.PARAMETROS, claves_de_piso()) == []

    @pytest.mark.parametrize("ruta", sorted(ARCHIVOS_SIN_PISO))
    def test_no_vacuidad_el_archivo_existe_tiene_cuerpo_y_la_guarda_ve_sus_imports(self, fuentes, ruta):
        que, minimo = ARCHIVOS_SIN_PISO[ruta]
        funciones = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(fuentes[ruta][1]))
        assert funciones >= minimo, f"{que} ({ruta}) tiene {funciones} funciones (minimo {minimo}): la guarda vigilaria nada"
        if ruta == MOTOR_PY:
            assert {"leer_pelicula", "escala_mm", "clase_resolucion"} <= set(importaciones_de_pelicula(fuentes, ruta)), "el motor importa el lector de pelicula.py: la guarda tiene que ver esos imports"
        if ruta == SERVICIO_PY:
            assert "leer_pelicula" in importaciones_de_pelicula(fuentes, ruta)

    def test_no_vacuidad_los_nombres_del_piso_se_derivan_de_pelicula_py_e_incluyen_los_del_plan(self, fuentes):
        nombres = nombres_del_piso(fuentes)
        assert set(NOMBRES_DEL_PLAN) <= nombres, f"del plan y no derivados: {sorted(set(NOMBRES_DEL_PLAN) - nombres)}"
        assert len(nombres) >= 60, f"solo {len(nombres)} nombres de piso derivados de pelicula.py"
        lector = {"leer_pelicula", "Pelicula", "clase_resolucion", "escala_mm", "CAPAS", "NOMBRE_DE_CAPA", "CAPA_POR_OMISION"}
        assert not (lector & nombres), f"el lector no es del piso: {sorted(lector & nombres)}"
        assert lector <= nombres_definidos(fuentes[PELICULA_PY][1])

    def test_no_vacuidad_las_claves_de_piso_se_derivan_de_los_diccionarios_y_ninguna_es_de_la_escala(self):
        claves = claves_de_piso()
        assert len(claves) >= 40 and "umbral_fondo" in claves and "pixeles_minimos" in claves
        from analisisImagenes import pelicula
        assert not (claves & set(pelicula.CLAVES_DE_LA_ESCALA))
        assert set(motor.PARAMETROS) >= set(pelicula.CLAVES_DE_LA_ESCALA), "el motor lleva las tres claves de la escala, que el piso comparte: no son claves de piso"

    @pytest.mark.parametrize("ruta", sorted(ARCHIVOS_SIN_PISO))
    @pytest.mark.parametrize("linea,que", [
        ("from analisisImagenes.pelicula import piso_de_pelicula", "import piso_de_pelicula"),
        ("from analisisImagenes.pelicula import Piso as P0", "import Piso"),
        ("from analisisImagenes.pelicula import *", "import *"),
        ("from analisisImagenes import pelicula as _p\ndef _por_si_acaso(x):\n    return _p.piso_de_pelicula(x, None, {})", "atributo .piso_de_pelicula"),
        ("def _por_si_acaso(x):\n    return PARAMETROS_DEL_PISO", "nombre PARAMETROS_DEL_PISO"),
        ("import analisisImagenes.pelicula as _q\ndef _por_si_acaso():\n    return getattr(_q, 'leer_referencia_virgen')", "cadena 'leer_referencia_virgen'"),
        ("from analisisImagenes.pelicula import texto_breve_del_piso", "import texto_breve_del_piso"),
        ("def _por_si_acaso():\n    return MODOS_DEL_PISO", "nombre MODOS_DEL_PISO"),
    ])
    def test_discrimina_cada_forma_de_usar_el_piso_en_cada_archivo(self, fuentes, ruta, linea, que):
        texto = fuentes[ruta][0] + "\n\n" + linea + "\n"
        con_piso = {**fuentes, ruta: (texto, ast.parse(texto))}
        usos = usos_del_piso(con_piso, ruta, nombres_del_piso(con_piso))
        assert usos and any(que in u[0] for u in usos), f"el guardia no ve `{que}` en {ruta}: {usos}"
        assert all(u[2] > len(fuentes[ruta][0].splitlines()) for u in usos), "lo que marca esta en el codigo agregado, no en el que ya habia"

    def test_el_guardia_nombra_la_funcion_del_uso(self, fuentes):
        texto = fuentes[MOTOR_PY][0] + "\n\ndef medir_con_piso(gris, clics, P):\n    from analisisImagenes.pelicula import piso_de_pelicula\n    return piso_de_pelicula(gris, clics, P)\n"
        usos = usos_del_piso({**fuentes, MOTOR_PY: (texto, ast.parse(texto))}, MOTOR_PY, nombres_del_piso(fuentes))
        assert {u[1] for u in usos} == {"medir_con_piso"}, usos

    def test_discrimina_una_clave_de_piso_en_el_parametros_del_motor(self):
        claves = claves_de_piso()
        assert claves_de_piso_en({**motor.PARAMETROS, "iqr_maximo": 15}, claves) == ["iqr_maximo"]
        assert claves_de_piso_en({**motor.PARAMETROS, "piso_manual": 1}, claves) == ["piso_manual"]
        assert claves_de_piso_en({**motor.PARAMETROS, "referencia_virgen": None}, claves) == ["referencia_virgen"]
        assert claves_de_piso_en({**motor.PARAMETROS, "pixeles_minimos": 2000}, claves) == ["pixeles_minimos"]

    def test_los_homonimos_inocentes_no_cuentan(self, fuentes):
        """Un nombre que solo se parece (una variable `modo`, la palabra «piso» en un comentario o una cadena larga) no es el piso: la guarda busca los nombres EXACTOS de `pelicula.py`."""
        texto = fuentes[MOTOR_PY][0] + "\n\ndef _inocente(modo, esquina):\n    # piso de la pelicula virgen\n    return 'el piso de la pelicula virgen no se usa', modo, esquina\n"
        assert usos_del_piso({**fuentes, MOTOR_PY: (texto, ast.parse(texto))}, MOTOR_PY, nombres_del_piso(fuentes)) == []


# ============================================================================================================================ los criterios discriminan (Trampa 8)
def _resultado_de_juguete(desfase_px=1.25, lado="derecha"):
    return {"angulo": 0.1, "x_ref": np.array([10.0, 10.5], np.float32), "lado_transito": lado,
            "contrastes_transito": {"izquierda": None, "derecha": {"banda": 180.0, "contraste": 13.0}},
            "perfiles": {"gris": {"estado": "ok", "desfase_px": desfase_px, "centros": np.array([1.0, 2.0])}}}


class TestLosCriteriosDeB3Discriminan:
    """Cada ayuda de `_ventanas_de_medida_braqui.py` que decide si una prueba pasa cae con un caso malo fabricado a mano y pasa con uno bueno."""

    def test_diferencias_ve_un_bit_un_elemento_un_tipo_una_clave_y_un_largo(self):
        a = _resultado_de_juguete()
        assert vm.diferencias(a, _resultado_de_juguete()) == []
        b = _resultado_de_juguete(desfase_px=float(np.nextafter(1.25, 2.0)))
        assert vm.diferencias(a, b) == ["/perfiles/gris/desfase_px: 1.25 != 1.2500000000000002"], "un bit de diferencia en un flotante"
        c = _resultado_de_juguete()
        c["perfiles"]["gris"]["centros"][1] = np.nextafter(2.0, 3.0)
        assert vm.diferencias(a, c) == ["/perfiles/gris/centros: 1 elementos distintos"]
        d = _resultado_de_juguete()
        d["x_ref"] = d["x_ref"].astype(np.float64)
        assert "tipo" in vm.diferencias(a, d)[0], "el mismo valor con otro tipo no es lo mismo"
        e = _resultado_de_juguete()
        e["contrastes_transito"]["izquierda"] = {"banda": 1.0}
        assert vm.diferencias(a, e), "una clave que era None"
        f = _resultado_de_juguete()
        del f["lado_transito"]
        assert "claves" in vm.diferencias(a, f)[0]
        assert vm.diferencias({"l": [1, 2]}, {"l": [1, 2, 3]}) == ["/l: largo distinto"]

    def test_diferencias_trata_un_nan_como_igual_a_otro_nan_y_respeta_lo_que_se_ignora(self):
        assert vm.diferencias({"v": float("nan"), "w": np.array([np.nan, 1.0])}, {"v": float("nan"), "w": np.array([np.nan, 1.0])}) == []
        assert vm.diferencias({"v": float("nan")}, {"v": 1.0}) != []
        a, b = _resultado_de_juguete(lado="derecha"), _resultado_de_juguete(lado="izquierda")
        assert vm.diferencias(a, b) and vm.diferencias(a, b, ignorar=("lado_transito",)) == []
        assert vm.diferencias(a, _resultado_de_juguete(desfase_px=9.0), ignorar=("lado_transito",)), "ignorar un lado no ignora los demas"

    def test_el_criterio_del_lado_solo_deja_pasar_el_mismo_o_sin_decidir(self):
        assert vm.fallos_del_lado("derecha", "derecha") == [] and vm.fallos_del_lado("izquierda", None) == []
        assert vm.fallos_del_lado("derecha", "izquierda"), "el contrario"
        assert vm.fallos_del_lado("izquierda", "derecha")
        assert vm.fallos_del_lado(None, None), "una placa que no decide el lado no prueba nada"
        assert vm.fallos_del_lado("centro", "centro"), "un lado que no existe"

    def test_la_ventana_declarada_de_una_linea_vertical_es_la_que_sale_a_mano(self):
        v = vm.ventana_corta([(100, 100), (100, 300)])
        assert v.centro == (100.0, 200.0) and v.mitad_ancha == 472.0 and v.mitad_larga == 100.0 + 71
        esquinas = {(round(float(x), 6), round(float(y), 6)) for x, y in v.esquinas()}
        assert esquinas == {(572.0, 29.0), (-372.0, 29.0), (-372.0, 371.0), (572.0, 371.0)}
        assert vm.ventana_larga([(100, 100), (100, 300)]).mitad_ancha == 1228.0
        horizontal = vm.ventana_corta([(100, 100), (300, 100)])
        assert {(round(float(x), 6), round(float(y), 6)) for x, y in horizontal.esquinas()} == {(29.0, 572.0), (29.0, -372.0), (371.0, -372.0), (371.0, 572.0)}, "la linea horizontal"

    def test_la_desviacion_de_la_ventana_cae_con_una_ventana_mas_ancha_mas_angosta_o_corrida(self):
        v = vm.ventana_corta([(100, 100), (100, 300)])
        ideal = v.esquinas()
        assert vm.desviacion_de_la_ventana(ideal, v) == pytest.approx(0.0, abs=1e-9)
        assert vm.desviacion_de_la_ventana(ideal + 1.1, v) <= 2.0, "~1 px de redondeo se acepta"
        centro = np.array(v.centro)
        assert vm.desviacion_de_la_ventana(centro + (ideal - centro) * 1.5, v) > 100, "una ventana 1.5 veces mas grande"
        assert vm.desviacion_de_la_ventana(centro + (ideal - centro) * 0.5, v) > 100, "una ventana a la mitad"
        assert vm.desviacion_de_la_ventana(ideal + np.array([5.0, 0.0]), v) > 2.0, "corrida 5 px"

    def test_la_mascara_dentro_marca_el_rectangulo_y_su_margen(self):
        chica = vm.LoDeclarado(ventana_mm=5.0, transito_mm=32.0, margen_filas_mm=10.0, resolucion_dpi=25.4)        # 1 mm = 1 px
        v = vm.ventana_corta([(50, 40), (50, 60)], chica)
        assert (v.mitad_larga, v.mitad_ancha) == (20.0, 5.0)
        m0 = vm.mascara_dentro(v, (100, 100), 0.0)
        assert m0[50, 50] and m0[30, 50] and m0[70, 50] and m0[50, 45] and m0[50, 55]
        assert not m0[28, 50] and not m0[72, 50] and not m0[50, 43] and not m0[50, 57]
        assert m0.sum() == pytest.approx(11 * 41, abs=60)
        m3 = vm.mascara_dentro(v, (100, 100), 3.0)
        assert m3[50, 42] and m3[50, 58] and m3[27, 50] and m3[73, 50] and not m3[50, 40] and not m3[24, 50]
        assert m3.sum() > m0.sum() and (m0 & ~m3).sum() == 0, "el margen solo agranda"

    def test_las_franjas_del_transito_son_lo_de_la_ventana_larga_que_no_esta_en_la_corta_repartido_por_lados(self):
        chica = vm.LoDeclarado(ventana_mm=10.0, transito_mm=32.0, margen_filas_mm=5.0, resolucion_dpi=25.4)        # 1 mm = 1 px: corta +-10, larga +-32, filas +-5
        clics = [(150, 50), (150, 150)]
        matriz = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        f = vm.franjas_del_transito(clics, (200, 300), matriz, declarado=chica)
        ys, xs = np.nonzero(f["izquierda"])
        assert xs.min() == 118 and xs.max() <= 137 and ys.min() >= 44 and ys.max() <= 156
        ys, xs = np.nonzero(f["derecha"])
        assert xs.max() == 182 and xs.min() >= 163
        assert not (f["izquierda"] & f["derecha"]).any() and ((f["izquierda"] | f["derecha"]) == f["ambas"]).all()
        assert not f["ambas"][100, 150] and not f["ambas"][100, 143], "la ventana corta (+ margen) no es franja"
        al_reves = vm.franjas_del_transito(clics, (200, 300), np.array([[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]), declarado=chica)
        assert (al_reves["izquierda"] == f["derecha"]).all(), "con la imagen girada media vuelta, «izquierda» y «derecha» se cambian"

    def test_pintar_pinta_solo_la_mascara_en_el_gris_y_en_cada_capa_de_color(self):
        gris = np.full((6, 6), 100, np.uint8)
        color = np.full((6, 6, 3), 100, np.uint8)
        mascara = np.zeros((6, 6), bool)
        mascara[2:4, 1:3] = True
        g2, c2 = vm.pintar(gris, color, mascara, {"gris": 7, "B": 11, "G": 22, "R": 33})
        assert (g2[mascara] == 7).all() and (g2[~mascara] == 100).all() and (gris == 100).all()
        assert (c2[mascara] == [11, 22, 33]).all() and (c2[~mascara] == 100).all() and (color == 100).all()

    def test_el_nivel_de_la_pelicula_es_la_mediana_de_la_pelicula_sin_dosis_y_no_cuenta_el_vacio_ni_la_meseta(self):
        resultado = {"perfiles": {c: {"tope": 255.0} for c in vm.CAPAS}}
        gris = np.full((70, 70), 250, np.uint8)               # pagina (invertido 5: no es pelicula)
        gris[:35, :35] = 120                                  # pelicula: invertido 135
        gris[35:, 35:] = 0                                    # meseta: invertido 255
        color = np.repeat(gris[:, :, None], 3, axis=2)
        niveles = vm.niveles_de_la_pelicula(gris, color, resultado, paso=1)
        assert niveles == {"gris": 120, "B": 120, "G": 120, "R": 120}
        with pytest.raises(ValueError):
            vm.niveles_de_la_pelicula(np.full((70, 70), 250, np.uint8), np.full((70, 70, 3), 250, np.uint8), resultado, paso=1)

    def _juguete_del_fondo(self):
        resultado = {"perfiles": {c: {"tope": 255.0} for c in vm.CAPAS}}
        gris = np.full((40, 40), 155, np.uint8)               # pelicula lejana: invertido 100
        gris[:5, :] = 10                                      # invertido 245: cerca de la meseta, no se toca
        gris[20:25, 20:25] = 150                              # zona protegida: no se toca
        color = np.repeat(gris[:, :, None], 3, axis=2).copy()
        protegida = np.zeros((40, 40), bool)
        protegida[20:25, 20:25] = True
        return resultado, gris, color, protegida

    def test_el_fondo_lejano_cambia_solo_la_pelicula_lejana_y_la_deja_lejos_de_los_umbrales(self):
        resultado, gris, color, protegida = self._juguete_del_fondo()
        for modo, valor, esperado in (("desplazar", 60.0, 255 - 160), ("desplazar", 500.0, 255 - 225), ("desplazar", -60.0, 255 - 40), ("plano", 0.0, 255), ("plano", 200.0, 255 - 200), ("plano", 250.0, 255 - 225)):
            g2, c2, cambiados, _ = vm.cambiar_el_fondo_lejano(gris, color, resultado, protegida, modo, valor)
            lejana = np.ones((40, 40), bool)
            lejana[:5, :] = False
            lejana[protegida] = False
            assert (g2[lejana] == esperado).all(), (modo, valor, np.unique(g2[lejana]))
            assert (g2[~lejana] == gris[~lejana]).all(), "ni la zona protegida ni lo que esta a menos de 20 niveles del tope se tocan"
            assert (c2[lejana] == esperado).all() and (c2[~lejana] == color[~lejana]).all()
            assert cambiados["gris"] == int(lejana.sum()) and (255.0 - g2[lejana] <= 255.0 - 30.0).all()
        assert (gris[10:15, 10:15] == 155).all() and (color[10:15, 10:15] == 155).all() and (gris[:5] == 10).all(), "las originales no se escriben"

    def test_el_fondo_lejano_cuenta_lo_que_cambia_dentro_de_la_ventana(self):
        resultado, gris, color, protegida = self._juguete_del_fondo()
        ventana = np.zeros((40, 40), bool)
        ventana[10:40, 10:40] = True
        _, _, cambiados, en_la_ventana = vm.cambiar_el_fondo_lejano(gris, color, resultado, protegida, "plano", 0.0, ventana)
        assert 0 < en_la_ventana["gris"] < cambiados["gris"] and en_la_ventana["gris"] == int(((~protegida) & ventana).sum())
        assert vm.cambiar_el_fondo_lejano(gris, color, resultado, protegida, "plano", 0.0)[3]["gris"] is None

    def test_la_zona_protegida_cubre_la_meseta_y_la_linea_y_deja_lo_lejano(self):
        alto, ancho = 100, 400
        x_ref = np.full(alto, 200.0)
        inicio = np.full(alto, -1)
        fin = np.full(alto, -1)
        inicio[40:60], fin[40:60] = 220, 260
        perfil = {"estado": "ok", "filas": np.arange(40, 60), "m": {"inicio": inicio, "fin": fin}}
        resultado = {"imagenes": {"gris": np.zeros((alto, ancho), np.float32)}, "x_ref": x_ref, "matriz_ventana": np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
                     "perfiles": {c: (perfil if c == "gris" else {"estado": "no medible"}) for c in vm.CAPAS}}
        z = vm.zona_protegida(resultado, (alto, ancho), distancia_a_la_meseta=30, distancia_a_la_linea=10)
        assert z[50, 240] and z[10, 240] and z[89, 240] and z[50, 190] and z[50, 289] and z[0, 205] and z[99, 195], "la caja de la meseta (+-30), la linea (+-10)"
        assert not z[0, 300] and not z[99, 100] and not z[5, 240] and not z[50, 5] and not z[50, 330], "lo lejano"
        sin_medidas = {**resultado, "perfiles": {c: {"estado": "no medible"} for c in vm.CAPAS}}
        with pytest.raises(ValueError):
            vm.zona_protegida(sin_medidas, (alto, ancho))

    def test_la_espia_registra_cada_ventana_que_pide_analizar_en_orden_con_lo_que_pidio_y_lo_que_armo_y_se_retira(self):
        """`vm.ventanas_que_arma_analizar` con un motor de juguete que arma dos ventanas de ancho conocido: las devuelve en orden, con lo que pidio cada llamada, y deja el motor como estaba."""
        motor_falso = types.SimpleNamespace()

        def ventana_rotada(gris, color, puntos, angulo, P, tam_mm, medio_ancho_mm=None, canales=("gris",), validos=None):
            return {"gris": np.zeros((5, 2 * int(medio_ancho_mm or 10) + 1), np.float32)}, np.zeros((2, 2)), np.eye(2, 3)

        def analizar(gris, color, dpi, puntos, parametros=None, validos=None):
            motor_falso.ventana_rotada(gris, color, puntos, 0.0, {}, 0.04)                                                                  # la de los desfases
            motor_falso.ventana_rotada(gris, color, puntos, 0.0, {}, 0.04, medio_ancho_mm=30, canales=("gris",), validos=validos)           # la larga del transito
            return "el resultado de analizar"
        motor_falso.ventana_rotada, motor_falso.analizar = ventana_rotada, analizar

        class EscenaFalsa:
            def medir(self, motor=None):
                return motor.analizar(None, None, 600, [], validos=None)
        armadas = vm.ventanas_que_arma_analizar(EscenaFalsa(), motor_falso)
        assert [v.imagenes["gris"].shape for v in armadas] == [(5, 21), (5, 61)], "las dos ventanas, en el orden en que analizar las pidio"
        assert armadas[0].kwargs == {} and armadas[1].kwargs == {"medio_ancho_mm": 30, "canales": ("gris",), "validos": None}
        assert armadas[1].matriz.shape == (2, 3) and armadas[1].clics.shape == (2, 2)
        assert motor_falso.ventana_rotada is ventana_rotada, "la espia se retira al terminar"

    def test_las_guardas_de_no_vacuidad_son_las_que_fija_esta_prueba(self):
        """Un umbral de no vacuidad que se afloja deja pasar una prueba en vacio: sus valores estan fijados aqui."""
        assert MINIMO_DE_PIXELES_PINTADOS == 100_000 and MINIMO_DE_PIXELES_QUE_CAMBIAN == 20_000
        assert MINIMO_DEL_FONDO_LEJANO_EN_LA_VENTANA == 20_000 and MINIMO_DEL_BLOQUE_NEGRO == 5_000
        assert vm.MARGEN_PX == 3 and vm.HOLGURA_BAJO_EL_TOPE == 20.0 and vm.TOPE_DEL_FONDO_CAMBIADO == 30.0
        assert vm.LO_DECLARADO == vm.LoDeclarado(ventana_mm=20.0, transito_mm=52.0, margen_filas_mm=3.0, resolucion_dpi=600.0)
        assert FONDOS_GLOBALES == (-30, -15, 0, 20, 50, 90) and len(POSICIONES_DEL_FONDO) == 4 and set(CAMBIOS_DEL_FONDO) == {"oscurece_60", "aclara_60", "plano_blanco", "plano_medio", "plano_oscuro"}

    def test_lo_medido_de_los_desfases_no_lleva_el_transito_ni_las_imagenes(self):
        e = construir("braqui_00")
        medido = vm.lo_medido_de_los_desfases(e.resultado, motor)
        assert "lado_transito" not in medido["valores"] and "imagenes" not in medido and "contrastes_transito" not in medido
        assert set(vm.CAPAS) <= set(medido) and all("sentido" not in medido[c + "/resumen"] for c in vm.CAPAS)
        assert medido["gris"]["desfase_px"] == e.resultado["perfiles"]["gris"]["desfase_px"] and "desfase_mm" in medido["gris/resumen"]
        assert {"angulo", "x_ref", "linea", "u_linea_px", "mensaje_linea", "valores"} <= set(medido), "la linea de referencia y su incertidumbre son parte de lo medido"
        assert {"estado", "filas", "desfase_px", "dispersion_px", "u_filas_px", "desfase_cruces_px", "centros", "desfases", "tope"} <= set(medido["gris"])
        assert {"desfase_gris_px", "desfase_gris_mm", "incertidumbre_gris_px", "filas_gris", "tamano_pixel_mm"} <= set(medido["valores"]), sorted(medido["valores"])
