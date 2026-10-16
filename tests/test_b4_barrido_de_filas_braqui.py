"""B.4 (PLAN_ANALISIS_PELICULAS_08-10.md, R11, H19, PD1, PD2): en la posicion inicial de braquiterapia el BARRIDO DE FILAS se ve y se dice cuando la regla se relaja.

CAUSA. El motor ya barre sin parametro (las filas cuya meseta tiene los dos bordes visibles y mide al menos el 80 % de la mas ancha) pero no mostraba el desfase de cada fila contra su posicion ni
decia cuando su regla se relaja: las filas dentro de un hueco puenteado de hasta 3 filas entran con cualquier cuerda y, si quedan menos de 10 filas, la fraccion baja al 30 %. Es DIBUJO Y TEXTO: ningun
numero cambia (`filas_utiles`, `medir_perfil`, `valores_medidos` y `resumen` son los de siempre; `VERSION_ALGORITMO` sigue en `PI-2`).

Que fija este archivo:
  PARTE DEL MOTOR (`motivos_de_las_filas`)
  1. El contrato: las filas con motivo «usada...» son EXACTAMENTE `filas_utiles(m, P)[0]` (en las peliculas reales, en las placas de PF.0 y en casos aleatorios), y el desfase por fila es el de `medir_perfil`
     (bit a bit en las filas usadas; su mediana es el `desfase_px` que se reporta).
  2. La regla de `filas_utiles` es la de HEAD: se compara con una copia LITERAL de la regla de antes de B.4 (referencia de la prueba, no del programa) en casos aleatorios.
  3. El vocabulario de motivos es cerrado y esta declarado una sola vez; el texto de los porcentajes esta atado a `PARAMETROS`.
  4. Cada motivo con un caso armado a mano (hueco puenteado, repliegue, sin meseta, borde tapado, cuerda corta, fuera del bloque central).
  PARTE DE LA PAGINA (`datos_del_barrido`, `dibujar_barrido_de_filas`, `texto_de_la_regla`, `_mostrar`)
  5. La grafica dibuja EXACTAMENTE las filas de `filas_utiles` (mismas posiciones y mismos desfases, en mm) y su mediana es la reportada (`desfase_px`); la media (discontinua) no lo es; las filas con
     meseta que no entran van aparte, en gris claro; las cuatro capas juntas comparten UNA referencia (la fila de la cuerda mas ancha del gris).
  6. La frase de la regla relajada: con el repliegue forzado (la placa de PF.0 de mancha chica) dice «se usaron N filas con menos del 80 % porque quedaban menos de 10» y con un hueco puenteado «M filas
     entraron por un hueco puenteado» (rojo: contra HEAD la pagina no dice nada); sin relajacion no dice nada; sin simbolos de correcto o incorrecto (DA-18).
  7. Por AST: ningun control de la pagina real esta conectado a los parametros de la regla del barrido (los cuatro nombres solo aparecen en `TRAZO_DE_PARAMETRO` y en `texto_de_la_regla`, que los LEE).
  8. El numero y el orden de los ejes de las dos figuras (gris: ventana, perfil, barrido; capas: R, G, B, barrido) estan declarados en constantes.
RONDA 2 DE LA REVISION (16-10; R2P-01 a R2P-05, SOLO pruebas; P-B4-01 no se corrige: B4-D3 queda como decision del fisico):
 13. La PAGINA REAL cablea bien sus dos graficas (clase `TestLaPaginaRealDibujaLosBarridos`, con EPSON009 y braqui_00): la pestaña del gris dibuja el barrido del GRIS y la de las capas el perfil de grises MAS
     una capa por cada capa medible, con la referencia del gris (R2P-01); cada una con SU color: TINTA para el gris y `COLOR_CAPA[capa]` para R, G y B, los cuatro distintos entre si, y el de su perfil en la misma
     figura (R2P-02); las filas que no entran son un gris CLARO como PROPIEDAD del color (mas claro que la tinta y que cada capa, casi sin saturacion), no la igualdad con la constante (R2P-03); los datos del barrido
     leen los parametros con que se midio el resultado, no los de omision (R2P-04: el caso del revisor, 0.5 / 25 sobre braqui_00, usa 116 filas en el gris y no las 72 de omision).
 14. R2P-05: lo que la pagina real DICE se prueba mirando la figura (el titulo, las lineas, la leyenda), con un oraculo que no usa la API nueva de B.4 (la frase esperada sale de `filas_utiles`, del ancho de cada
     fila y de los parametros del resultado): contra HEAD esas pruebas caen por una aserción sobre lo que la pagina dibuja y no por un `AttributeError` al llamar a una funcion que HEAD no tiene (las pruebas de
     las funciones nuevas siguen cayendo por su ausencia: es el rojo de un TDD sobre una API nueva).
RONDA 1 DE LA REVISION (16-10; R1-01 a R1-08):
  9. Las cuatro capas juntas: las ordenadas de cada capa y su linea de mediana se LEEN de la figura y se comparan con `desfases * tam` de `medir_perfil` y con `resumen()['desfase_mm']` (con una imagen real
     y una sintetica), y tambien sin escala (ejes y rotulos en px); un caso donde la capa que DICE el hueco puenteado es una capa dibujada (EPSON009, la roja).
 10. Las fronteras de la regla: una cuerda EXACTAMENTE al 80 % del maximo es «usada» (no «por un hueco puenteado») y una al 30 % entra en el repliegue, a mano y en casos aleatorios que las incluyen.
 11. Un repliegue que solo suma filas de OTRO bloque con cuerdas de 80 % o mas tambien se dice (B4-D7); los textos de los motivos no llevan cifras (R1-07) y la frase lee los parametros con que se midio.
 12. La leyenda del barrido va FUERA de los ejes (a su derecha), dentro de la figura, y no tapa ninguna fila usada (R1-08).
Trampa 9: las paginas se cierran con la receta completa (la fixture `fabrica` de PI.4). Trampa 10: ningun `lru_cache`; los resultados caros son fixtures de modulo."""
import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

import _placa_braqui_sintetica as pf0
from analisisImagenes import posicion_inicial_braqui as motor
from services import posicion_inicial_braqui as svc
from test_pi1_motor_posicion_inicial import CLICS_EPSON009, CLICS_PLACA_REAL
from test_pi3_servicio_posicion_inicial import BRAQUI_00, EPSON009, bd, plantilla  # noqa: F401  (fixtures de PI.3: la pagina las necesita)

PERFILES = ("gris", "R", "G", "B")
P0 = dict(motor.PARAMETROS)


# ------------------------------------------------------------------------------------------------------ ayudas

def _regla_de_head(m, P):
    """COPIA LITERAL de `filas_utiles` tal como estaba antes de B.4 (76be8ad): la referencia contra la que se prueba que el refactor no cambio cuales filas entran. Vive aqui, no en el programa."""
    inicio, fin, oculto = m["inicio"], m["fin"], m["oculto"]
    ancho = np.where(inicio >= 0, fin - inicio + 1, 0)
    if np.max(ancho) == 0:
        return np.array([], int), ancho
    candidatas = np.where(ancho >= P["fraccion_central"] * np.max(ancho))[0]
    inis, fins = motor.corridas(np.isin(np.arange(len(ancho)), candidatas), 3)
    mas_ancha = int(np.argmax(ancho))
    k = int(np.where((inis <= mas_ancha) & (fins >= mas_ancha))[0][0])
    bloque = np.arange(inis[k], fins[k] + 1)
    filas = bloque[(ancho[bloque] > 0) & ~oculto[bloque]]
    if len(filas) < P["minimo_filas"]:
        filas = np.where((inicio >= 0) & ~oculto & (ancho >= P["fraccion_minima"] * np.max(ancho)))[0]
    return filas, ancho


def _m(anchos, ocultas=(), centro=100.0):
    """Un `m` armado a mano con las claves que lee la regla: una fila por ancho (0 = sin meseta), centrada en `centro`, con las filas de `ocultas` con el borde tapado."""
    anchos = np.asarray(anchos, int)
    n = len(anchos)
    inicio = np.where(anchos > 0, (centro - anchos / 2.0).astype(int), -1)
    fin = np.where(anchos > 0, inicio + anchos - 1, -1)
    oculto = np.zeros(n, bool)
    oculto[list(ocultas)] = True
    return {"inicio": inicio, "fin": fin, "oculto": oculto,
            "x_izq": np.where(anchos > 0, inicio - 0.5, np.nan), "x_der": np.where(anchos > 0, fin + 0.5, np.nan)}


def _motivos(anchos, ocultas=()):
    return motor.motivos_de_las_filas(_m(anchos, ocultas), P0)["motivos"]


@pytest.fixture(scope="module")
def resultados():
    """El analisis de las dos peliculas reales y de tres placas de PF.0, una sola vez (los dibujos no lo modifican)."""
    salida = {"braqui_00": svc.analizar_imagen(BRAQUI_00, CLICS_PLACA_REAL), "EPSON009": svc.analizar_imagen(EPSON009, CLICS_EPSON009)}
    for d in (-2.0, 0.0, 1.5):
        p = pf0.generar_independiente(d, formato="png")
        salida[f"PF0/independiente/{d:+.1f}"] = svc.analizar_imagen(p.datos, [tuple(c) for c in p.clics])
    return salida


# ------------------------------------------------------------------------------------------------------ 1. el contrato

class TestElContratoConLasFilasQueEntran:
    def test_las_filas_usadas_son_exactamente_filas_utiles_en_todas_las_peliculas_y_placas(self, resultados):
        for nombre, r in resultados.items():
            for perfil in PERFILES:
                perfil_r = r["perfiles"][perfil]
                d = motor.motivos_de_las_filas(perfil_r["m"], r["parametros"], r["x_ref"])
                filas, ancho = motor.filas_utiles(perfil_r["m"], r["parametros"])
                assert np.array_equal(np.where(d["usada"])[0], filas), (nombre, perfil)
                assert np.array_equal(d["ancho"], ancho), (nombre, perfil)
                assert np.array_equal(np.where(d["usada"])[0], perfil_r["filas"]), (nombre, perfil)

    def test_todo_motivo_de_una_fila_usada_dice_usada_y_el_de_una_fila_no_usada_dice_no_entra(self, resultados):
        for nombre, r in resultados.items():
            for perfil in PERFILES:
                d = motor.motivos_de_las_filas(r["perfiles"][perfil]["m"], r["parametros"], r["x_ref"])
                for usada, motivo in zip(d["usada"], d["motivos"]):
                    assert (motivo in motor.MOTIVOS_DE_FILAS_USADAS) == bool(usada), (nombre, perfil, motivo)
                    assert motivo.startswith("usada") if usada else motivo.startswith("no entra: ")

    def test_el_desfase_por_fila_es_el_de_medir_perfil_bit_a_bit_y_su_mediana_es_la_que_se_reporta(self, resultados):
        for nombre, r in resultados.items():
            for perfil in PERFILES:
                perfil_r = r["perfiles"][perfil]
                if perfil_r["estado"] != "ok":
                    continue
                d = motor.motivos_de_las_filas(perfil_r["m"], r["parametros"], r["x_ref"])
                assert np.array_equal(d["desfase"][d["usada"]], perfil_r["desfases"]), (nombre, perfil)      # exacto, no aproximado
                assert float(np.median(d["desfase"][d["usada"]])) == perfil_r["desfase_px"], (nombre, perfil)

    def test_el_desfase_existe_en_toda_fila_con_meseta_usada_o_no_y_es_nan_donde_no_hay_meseta(self, resultados):
        for nombre, r in resultados.items():
            m = r["perfiles"]["gris"]["m"]
            d = motor.motivos_de_las_filas(m, r["parametros"], r["x_ref"])
            assert np.array_equal(np.isnan(d["desfase"]), ~d["con_meseta"]), nombre
            esperado = r["x_ref"] - (m["x_izq"] + m["x_der"]) / 2.0
            assert np.array_equal(d["desfase"][d["con_meseta"]], esperado[d["con_meseta"]]), nombre

    def test_sin_x_ref_no_hay_desfase_y_el_resto_es_igual(self, resultados):
        r = resultados["braqui_00"]
        m = r["perfiles"]["gris"]["m"]
        sin = motor.motivos_de_las_filas(m, r["parametros"])
        con = motor.motivos_de_las_filas(m, r["parametros"], r["x_ref"])
        assert "desfase" not in sin and "desfase" in con
        assert sin["motivos"] == con["motivos"] and np.array_equal(sin["usada"], con["usada"])

    def test_la_fila_de_referencia_es_la_de_la_cuerda_mas_ancha_y_esta_entre_las_usadas(self, resultados):
        for nombre, r in resultados.items():
            for perfil in PERFILES:
                d = motor.motivos_de_las_filas(r["perfiles"][perfil]["m"], r["parametros"], r["x_ref"])
                assert d["fila_de_referencia"] == int(np.argmax(d["ancho"])), (nombre, perfil)
                if not d["repliegue"] and d["usada"].any():
                    assert d["usada"][d["fila_de_referencia"]] or d["motivos"][d["fila_de_referencia"]] == motor.MOTIVO_BORDE_TAPADO

    def test_motivos_de_las_filas_no_modifica_lo_que_recibe(self, resultados):
        r = resultados["braqui_00"]
        m = r["perfiles"]["gris"]["m"]
        copia = {k: np.array(v, copy=True) for k, v in m.items() if isinstance(v, np.ndarray)}
        motor.motivos_de_las_filas(m, r["parametros"], r["x_ref"])
        for k, v in copia.items():
            assert np.array_equal(m[k], v, equal_nan=True), k


# ------------------------------------------------------------------------------------------------------ 2. la regla es la de HEAD

class TestLaReglaNoCambia:
    def test_filas_utiles_es_la_regla_de_head_en_casos_aleatorios(self):
        azar = np.random.default_rng(20261015)
        for _ in range(400):
            n = int(azar.integers(5, 90))
            anchos = azar.choice([0, 0, 10, 25, 40, 70, 90, 100], size=n) * azar.choice([1, 1, 1, 0.5], size=n)
            ocultas = [int(i) for i in azar.integers(0, n, size=int(azar.integers(0, 6)))]
            m = _m(np.round(anchos).astype(int), ocultas)
            esperado, ancho_e = _regla_de_head(m, P0)
            filas, ancho = motor.filas_utiles(m, P0)
            assert np.array_equal(filas, esperado) and filas.dtype == esperado.dtype
            assert np.array_equal(ancho, ancho_e)
            assert np.array_equal(np.where(motor.motivos_de_las_filas(m, P0)["usada"])[0], esperado)

    def test_filas_utiles_es_la_regla_de_head_con_filas_exactamente_en_las_fronteras(self):
        """R1-04: la prueba de arriba no tenia NINGUNA fila exactamente al 80 % ni al 30 % del maximo (0 de 400: sus anchos son ocho valores fijos), asi que cambiar `>=` por `>` en la regla no la hacia caer
        (solo la mataba test_pi1). Aqui las fronteras entran A PROPOSITO: cada caso lleva el maximo, filas exactamente al 80 % y al 30 % de el, y otras justo por encima y por debajo, y se compara con la
        copia literal de la regla de HEAD y, fila por fila, con lo que dice el vocabulario (una fila usada es «usada» si y solo si llega al 80 % del maximo)."""
        azar = np.random.default_rng(20261016)
        con_80 = con_30 = 0
        for _ in range(400):
            n = int(azar.integers(8, 70))
            tope = int(azar.choice([50, 100, 200]))
            valores = np.array([0, 0, tope * 3 // 10 - 1, tope * 3 // 10, tope * 3 // 10 + 1, tope // 2, tope * 8 // 10 - 1, tope * 8 // 10, tope * 8 // 10 + 1, tope])
            anchos = azar.choice(valores, size=n)
            anchos[int(azar.integers(0, n))] = tope                                  # el maximo EXISTE: las fronteras se miden contra el
            ocultas = [int(i) for i in azar.integers(0, n, size=int(azar.integers(0, 4)))]
            m = _m(anchos, ocultas)
            esperado, ancho_e = _regla_de_head(m, P0)
            filas, ancho = motor.filas_utiles(m, P0)
            assert np.array_equal(filas, esperado) and np.array_equal(ancho, ancho_e)
            d = motor.motivos_de_las_filas(m, P0)
            assert np.array_equal(np.where(d["usada"])[0], esperado)
            maximo = float(anchos.max())
            con_80 += bool(np.any(anchos == P0["fraccion_central"] * maximo))
            con_30 += bool(np.any(anchos == P0["fraccion_minima"] * maximo))
            for y in np.where(d["usada"])[0]:
                assert (d["motivos"][y] == motor.MOTIVO_USADA) == bool(anchos[y] >= P0["fraccion_central"] * maximo), (anchos.tolist(), int(y), d["motivos"][y])
        assert con_80 > 300 and con_30 > 300, f"las fronteras tienen que estar en casi todos los casos (80 %: {con_80}, 30 %: {con_30} de 400)"

    def test_filas_utiles_es_la_regla_de_head_en_las_peliculas_reales(self, resultados):
        for nombre, r in resultados.items():
            for perfil in PERFILES:
                m = r["perfiles"][perfil]["m"]
                esperado, ancho_e = _regla_de_head(m, r["parametros"])
                filas, ancho = motor.filas_utiles(m, r["parametros"])
                assert np.array_equal(filas, esperado) and np.array_equal(ancho, ancho_e), (nombre, perfil)


# ------------------------------------------------------------------------------------------------------ 3. el vocabulario

class TestElVocabularioDeMotivos:
    def test_el_vocabulario_esta_declarado_una_sola_vez_y_cada_motivo_es_distinto(self):
        todos = [motor.MOTIVO_USADA, motor.MOTIVO_USADA_POR_HUECO, motor.MOTIVO_USADA_POR_REPLIEGUE, motor.MOTIVO_SIN_MESETA, motor.MOTIVO_BORDE_TAPADO,
                 motor.MOTIVO_CUERDA_CORTA, motor.MOTIVO_CUERDA_CORTA_EN_REPLIEGUE, motor.MOTIVO_FUERA_DEL_BLOQUE]
        assert tuple(todos) == motor.MOTIVOS_DE_FILAS and len(set(todos)) == len(todos) == 8
        assert motor.MOTIVOS_DE_FILAS_USADAS == tuple(todos[:3])

    def test_ningun_texto_de_motivo_lleva_una_cifra_que_la_regla_pueda_cambiar(self):
        """R1-07: los motivos decian «80 %» y «30 %» fijos aunque la regla se midiera con otra fraccion («no entra: cuerda menor del 80 %» para una cuerda al 60 % medida con el 70 %). Los textos no llevan
        ninguna cifra (una sola definicion, ninguna puede discrepar de PARAMETROS) y las cifras se dicen donde se muestran, leidas de los parametros con que se midio (la frase de la regla: ver abajo)."""
        for motivo in motor.MOTIVOS_DE_FILAS:
            assert not re.search(r"\d", motivo), f"el motivo {motivo!r} lleva una cifra: seria falso en cuanto la regla se midiera con otra fraccion"

    def test_con_otras_fracciones_los_motivos_clasifican_con_ellas_y_siguen_sin_cifras(self):
        """R1-07 (la prueba que varia P): una cuerda al 75 % es corta con el 80 % y ANCHA con el 70 % (otro bloque); los textos devueltos no llevan cifra en ninguno de los dos casos y no discrepan."""
        anchos = [100] * 12 + [0] * 5 + [75] * 12
        P70 = dict(P0, fraccion_central=0.7, fraccion_minima=0.2)
        con_80, con_70 = motor.motivos_de_las_filas(_m(anchos), P0)["motivos"], motor.motivos_de_las_filas(_m(anchos), P70)["motivos"]
        assert con_80[17] == motor.MOTIVO_CUERDA_CORTA and con_70[17] == motor.MOTIVO_FUERA_DEL_BLOQUE
        for motivos in (con_80, con_70):
            assert set(motivos) <= set(motor.MOTIVOS_DE_FILAS) and not [t for t in motivos if re.search(r"\d", t)]

    def test_el_motor_solo_devuelve_motivos_del_vocabulario(self, resultados):
        for nombre, r in resultados.items():
            for perfil in PERFILES:
                d = motor.motivos_de_las_filas(r["perfiles"][perfil]["m"], r["parametros"], r["x_ref"])
                assert set(d["motivos"]) <= set(motor.MOTIVOS_DE_FILAS), (nombre, perfil)
        azar = np.random.default_rng(7)
        for _ in range(200):
            n = int(azar.integers(5, 70))
            m = _m(azar.choice([0, 12, 30, 60, 95, 100], size=n), [int(i) for i in azar.integers(0, n, size=3)])
            assert set(motor.motivos_de_las_filas(m, P0)["motivos"]) <= set(motor.MOTIVOS_DE_FILAS)

    def test_sin_meseta_en_ninguna_fila_todas_dicen_sin_meseta_y_no_hay_referencia(self):
        d = motor.motivos_de_las_filas(_m([0] * 20), P0)
        assert d["motivos"] == [motor.MOTIVO_SIN_MESETA] * 20 and not d["usada"].any() and d["fila_de_referencia"] == -1 and not d["repliegue"]


# ------------------------------------------------------------------------------------------------------ 4. cada motivo, a mano

class TestCadaMotivoConUnCasoArmadoAMano:
    def test_un_bloque_limpio_de_cuerdas_anchas_son_todas_usadas(self):
        motivos = _motivos([0] * 4 + [100] * 12 + [0] * 4)
        assert motivos == [motor.MOTIVO_SIN_MESETA] * 4 + [motor.MOTIVO_USADA] * 12 + [motor.MOTIVO_SIN_MESETA] * 4

    def test_un_hueco_de_hasta_tres_filas_entra_con_cualquier_cuerda_y_lo_dice(self):
        motivos = _motivos([100] * 8 + [50] * 3 + [100] * 8)
        assert motivos == [motor.MOTIVO_USADA] * 8 + [motor.MOTIVO_USADA_POR_HUECO] * 3 + [motor.MOTIVO_USADA] * 8

    def test_un_hueco_de_cuatro_filas_ya_no_se_puentea_y_deja_el_bloque_de_la_mas_ancha(self):
        motivos = _motivos([100] * 12 + [50] * 4 + [100] * 8)
        assert motivos == [motor.MOTIVO_USADA] * 12 + [motor.MOTIVO_CUERDA_CORTA] * 4 + [motor.MOTIVO_FUERA_DEL_BLOQUE] * 8

    def test_un_hueco_sin_meseta_dentro_del_bloque_no_entra_y_dice_sin_meseta(self):
        motivos = _motivos([100] * 8 + [0] * 2 + [100] * 8)
        assert motivos == [motor.MOTIVO_USADA] * 8 + [motor.MOTIVO_SIN_MESETA] * 2 + [motor.MOTIVO_USADA] * 8

    def test_un_borde_tapado_por_la_linea_no_entra_aunque_la_cuerda_sea_ancha(self):
        motivos = _motivos([100] * 14, ocultas=(3, 4))
        assert motivos[3] == motivos[4] == motor.MOTIVO_BORDE_TAPADO
        assert [m for i, m in enumerate(motivos) if i not in (3, 4)] == [motor.MOTIVO_USADA] * 12

    def test_una_fila_corta_y_tapada_dice_borde_tapado_porque_esa_razon_vale_tambien_en_el_repliegue(self):
        motivos = _motivos([100] * 12 + [20] * 4 + [100] * 8, ocultas=(13,))
        assert motivos[13] == motor.MOTIVO_BORDE_TAPADO and motivos[12] == motor.MOTIVO_CUERDA_CORTA

    def test_con_menos_de_diez_filas_se_repliega_al_30_por_ciento_y_lo_dice(self):
        motivos = _motivos([40] * 6 + [100] * 5 + [40] * 6 + [20] * 3)
        assert motivos == [motor.MOTIVO_USADA_POR_REPLIEGUE] * 6 + [motor.MOTIVO_USADA] * 5 + [motor.MOTIVO_USADA_POR_REPLIEGUE] * 6 + [motor.MOTIVO_CUERDA_CORTA_EN_REPLIEGUE] * 3
        assert motor.motivos_de_las_filas(_m([40] * 6 + [100] * 5 + [40] * 6), P0)["repliegue"] is True

    def test_en_el_repliegue_el_borde_tapado_y_la_falta_de_meseta_siguen_sin_entrar(self):
        motivos = _motivos([40] * 4 + [0] * 2 + [100] * 5 + [40] * 6, ocultas=(0,))
        assert motivos[0] == motor.MOTIVO_BORDE_TAPADO and motivos[4] == motivos[5] == motor.MOTIVO_SIN_MESETA
        assert motivos[1] == motor.MOTIVO_USADA_POR_REPLIEGUE and motivos[6] == motor.MOTIVO_USADA

    def test_una_fila_con_la_cuerda_exacta_al_80_por_ciento_del_maximo_es_usada_y_la_apenas_menor_no(self):
        """R1-04: la frontera del 80 % es de las cuerdas anchas (`>=`). Con `>` una cuerda al 80 % dentro del bloque se rotularia «usada por un hueco puenteado» y la frase de la pagina diria falsamente que
        una fila entro por un hueco puenteado."""
        assert _motivos([100] * 8 + [80] + [100] * 8)[8] == motor.MOTIVO_USADA
        assert _motivos([100] * 8 + [79] + [100] * 8)[8] == motor.MOTIVO_USADA_POR_HUECO
        # fuera del bloque central (cinco filas sin meseta, mas que el hueco que se puentea): la del 80 % era ancha pero quedo en otro bloque; la del 79 % era corta
        assert _motivos([100] * 12 + [0] * 5 + [80] * 3)[17:] == [motor.MOTIVO_FUERA_DEL_BLOQUE] * 3
        assert _motivos([100] * 12 + [0] * 5 + [79] * 3)[17:] == [motor.MOTIVO_CUERDA_CORTA] * 3
        # y el 80 % exacto cuenta para llegar a las diez filas del bloque (sin repliegue); el 79 % no (con repliegue)
        con_80 = motor.motivos_de_las_filas(_m([100] * 5 + [80] * 5), P0)
        assert con_80["repliegue"] is False and con_80["motivos"] == [motor.MOTIVO_USADA] * 10
        con_79 = motor.motivos_de_las_filas(_m([100] * 5 + [79] * 5), P0)
        assert con_79["repliegue"] is True and con_79["motivos"] == [motor.MOTIVO_USADA] * 5 + [motor.MOTIVO_USADA_POR_REPLIEGUE] * 5

    def test_en_el_repliegue_la_cuerda_exacta_al_30_por_ciento_entra_y_la_apenas_menor_no(self):
        """R1-04: la frontera del 30 % del repliegue tambien es `>=`."""
        motivos = _motivos([100] * 5 + [30] * 6 + [29] * 2)
        assert motivos == [motor.MOTIVO_USADA] * 5 + [motor.MOTIVO_USADA_POR_REPLIEGUE] * 6 + [motor.MOTIVO_CUERDA_CORTA_EN_REPLIEGUE] * 2

    def test_el_motor_dice_cuales_filas_estan_en_el_bloque_central(self):
        """R1-05: el repliegue que suma filas de otro bloque se dice con un conteo; el dato (que filas son del bloque central) lo da el motor, el mismo con que `filas_utiles` elige las suyas."""
        d = motor.motivos_de_las_filas(_m([50] * 6 + [0] * 4 + [50] * 6), P0)
        assert d["repliegue"] is True and d["en_bloque"].tolist() == [True] * 6 + [False] * 10
        assert d["usada"].tolist() == [True] * 6 + [False] * 4 + [True] * 6
        assert motor.motivos_de_las_filas(_m([100] * 12), P0)["en_bloque"].tolist() == [True] * 12
        assert not motor.motivos_de_las_filas(_m([0] * 5), P0)["en_bloque"].any()

    def test_sin_repliegue_toda_fila_usada_esta_en_el_bloque_central_en_las_peliculas_y_placas(self, resultados):
        for nombre, r in resultados.items():
            for perfil in PERFILES:
                d = motor.motivos_de_las_filas(r["perfiles"][perfil]["m"], r["parametros"])
                if not d["repliegue"]:
                    assert not (d["usada"] & ~d["en_bloque"]).any(), (nombre, perfil)

    def test_sin_repliegue_el_indicador_es_falso_y_con_diez_filas_justas_tampoco_se_repliega(self):
        assert motor.motivos_de_las_filas(_m([100] * 10), P0)["repliegue"] is False
        assert motor.motivos_de_las_filas(_m([100] * 9), P0)["repliegue"] is True


# ====================================================================================================== LA PAGINA (B.4)

import ast
import colorsys
from pathlib import Path

from matplotlib.colors import to_rgb
from matplotlib.figure import Figure

import ui.paginasControles.PruebasMensuales.posicion_inicial_braqui as pagina_mod
from test_pi4_pagina_posicion_inicial import _analizada, _cursor_limpio, app, archivo_braqui, dialogos, fabrica, pagina  # noqa: F401  (fixtures de PI.4)

PAGINA_PY = Path(__file__).resolve().parents[1] / "ui" / "paginasControles" / "PruebasMensuales" / "posicion_inicial_braqui.py"
TAM = 25.4 / 600.0
PELICULAS_REALES = {"braqui_00": (BRAQUI_00, CLICS_PLACA_REAL), "EPSON009": (EPSON009, CLICS_EPSON009)}       # la de la capa roja que no se mide y la que mide sus cuatro capas
COLORES_DE_LA_PAGINA = (pagina_mod.TINTA, *pagina_mod.COLOR_CAPA.values())       # con lo que se dibuja lo demas: el «gris claro» de las filas que no entran tiene que superarlos en claridad


def _eje():
    return Figure().add_subplot()


def _lineas(eje, etiqueta):
    return [l for l in eje.lines if l.get_label() == etiqueta]


def _linea_del_perfil(eje):
    """La linea del perfil filtrado de un eje de `dibujar_perfil`: la que lleva el color de su capa (el perfil de grises va en la tinta). Sirve de referencia independiente del color de cada capa en el barrido:
    las dos graficas de una misma figura tienen que usar el mismo color para la misma capa."""
    lineas = _lineas(eje, "perfil con filtro de mediana")
    assert len(lineas) == 1, "el eje no es un perfil de B.1"
    return lineas[0]


def _luminosidad(color):
    """La luminosidad (HLS, de 0 negro a 1 blanco) de un color de matplotlib."""
    return colorsys.rgb_to_hls(*to_rgb(color))[1]


def _saturacion(color):
    """La saturacion (HSV, de 0 gris a 1 color puro) de un color de matplotlib."""
    return colorsys.rgb_to_hsv(*to_rgb(color))[1]


def _es_gris_claro(color, contra=()):
    """«Gris claro» como PROPIEDAD del color (R2P-03: compararlo con la constante de la pagina no cae si la constante pasa a negro): los tres canales altos (>= 0.70), casi sin saturacion (<= 0.12) y mas
    claro (luminosidad) que cada color de `contra` (la tinta y las tres capas, que son los colores con que se dibuja lo demas)."""
    return min(to_rgb(color)) >= 0.70 and _saturacion(color) <= 0.12 and all(_luminosidad(color) > _luminosidad(c) for c in contra)


def _predomina(color, canal):
    """El canal (0 rojo, 1 verde, 2 azul) domina con claridad el color: «el color de la capa roja es rojizo» sin compararlo con `COLOR_CAPA`."""
    rgb = to_rgb(color)
    return rgb[canal] - max(rgb[i] for i in range(3) if i != canal) >= 0.15


def _filas_con_menos_de_la_fraccion(resultado, perfil):
    """Cuantas filas USADAS tienen una cuerda menor que `fraccion_central` del maximo (oraculo de la prueba con `filas_utiles` y el ancho, nada de la API nueva de B.4): con el repliegue son las que el repliegue
    sumo y sin el son las que entraron por un hueco puenteado."""
    filas, ancho = motor.filas_utiles(resultado["perfiles"][perfil]["m"], resultado["parametros"])
    return int(np.sum(ancho[filas] < resultado["parametros"]["fraccion_central"] * ancho.max()))


def _resultado_falso(anchos, parametros=None):
    """Un resultado con UN perfil medible («gris») armado a mano con las claves que leen `datos_del_barrido`, `texto_de_la_regla` y `dibujar_barrido_de_filas` (para probar la frase y el titulo sin
    una pelicula): las filas son las de `_m(anchos)`, el desfase de cada una el de sus bordes contra una linea en x = 0."""
    m = _m(anchos)
    n = len(m["inicio"])
    return {"perfiles": {"gris": {"m": m, "estado": "ok", "desfase_px": 0.0}}, "parametros": dict(P0 if parametros is None else parametros), "x_ref": np.zeros(n), "tamano_pixel_mm": TAM}


@pytest.fixture(scope="module")
def placa_chica():
    """La placa de PF.0 de mancha chica (independiente del motor): fuerza el repliegue al 30 % en el gris y en las tres capas (medido en la captura del oraculo de B.4)."""
    p = pf0.generar("independiente", "mancha_chica", 1.0)
    return p, svc.analizar_imagen(p.datos, [tuple(c) for c in p.clics])


@pytest.fixture(scope="module")
def placa_con_repliegue_medible():
    """La placa principal de PF.0 a +1.5 mm (independiente del motor): el gris y la capa verde se miden («ok») y entran por el repliegue al 30 % (medido: 11 y 12 filas con menos del 80 %)."""
    p = pf0.generar_independiente(1.5, formato="png")
    return p, svc.analizar_imagen(p.datos, [tuple(c) for c in p.clics])


class TestLaGraficaDibujaLasFilasQueEntraron:
    def test_las_posiciones_y_los_desfases_son_los_de_las_filas_de_filas_utiles(self, resultados):
        for nombre, r in resultados.items():
            tam = r["tamano_pixel_mm"]
            for perfil in PERFILES:
                perfil_r = r["perfiles"][perfil]
                if perfil_r["estado"] != "ok":
                    continue
                d = pagina_mod.datos_del_barrido(r, perfil)
                ref = int(np.argmax(motor.filas_utiles(perfil_r["m"], r["parametros"])[1]))
                assert np.array_equal(d["filas"][d["usada"]], perfil_r["filas"]), (nombre, perfil)
                assert np.array_equal(d["posicion"][d["usada"]], (perfil_r["filas"] - ref) * tam), (nombre, perfil)
                assert np.array_equal(d["desfase"][d["usada"]], perfil_r["desfases"] * tam), (nombre, perfil)
                assert d["unidad"] == "mm"

    def test_la_mediana_es_la_que_se_reporta_y_la_media_no(self, resultados):
        for nombre, r in resultados.items():
            for perfil in PERFILES:
                if r["perfiles"][perfil]["estado"] != "ok":
                    continue
                d = pagina_mod.datos_del_barrido(r, perfil)
                s = motor.resumen(r, perfil)
                assert d["mediana"] == pytest.approx(s["desfase_mm"], abs=1e-12), (nombre, perfil)
                assert d["media"] != d["mediana"], (nombre, perfil)           # control: la media existe y no es la reportada
                assert d["media"] == pytest.approx(float(np.mean(d["desfase"][d["usada"]])))

    def test_dibujar_pone_las_filas_usadas_las_que_no_entran_la_mediana_punteada_y_la_media_discontinua(self, resultados):
        r = resultados["braqui_00"]
        d = pagina_mod.datos_del_barrido(r, "gris")
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r, ("gris",))
        usadas = _lineas(eje, "filas usadas")
        assert len(usadas) == 1 and np.array_equal(usadas[0].get_xdata(), d["posicion"][d["usada"]]) and np.array_equal(usadas[0].get_ydata(), d["desfase"][d["usada"]])
        assert usadas[0].get_linestyle() == "None" and usadas[0].get_marker() == "o", "un perfil: solo puntos (barrido automatico: AUTO-P672)"
        fuera = _lineas(eje, "filas con meseta que no entran")
        assert len(fuera) == 1 and len(fuera[0].get_xdata()) == int((~d["usada"]).sum()) > 0
        assert np.array_equal(fuera[0].get_ydata(), d["desfase"][~d["usada"]])
        assert fuera[0].get_color() == pagina_mod.COLOR_FILA_QUE_NO_ENTRA and _es_gris_claro(fuera[0].get_color(), COLORES_DE_LA_PAGINA)      # R2P-03: la constante no basta, el plan pide un gris CLARO
        mediana, media = _lineas(eje, "mediana (la que se reporta)"), _lineas(eje, "media")
        assert len(mediana) == 1 and mediana[0].get_linestyle() == ":" and mediana[0].get_ydata()[0] == d["mediana"]
        assert len(media) == 1 and media[0].get_linestyle() == "--" and media[0].get_ydata()[0] == d["media"]
        assert eje.get_xlabel() == "posición de la fila respecto de la cuerda más ancha [mm]" and eje.get_ylabel() == "desfase [mm]"

    def test_las_cuatro_capas_juntas_comparten_la_referencia_del_gris_y_la_que_no_se_mide_lo_dice(self, resultados):
        r = resultados["braqui_00"]
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r, ("gris", "R", "G", "B"))
        ref_gris = motor.motivos_de_las_filas(r["perfiles"]["gris"]["m"], r["parametros"])["fila_de_referencia"]
        assert "del gris" in eje.get_xlabel()
        assert r["perfiles"]["R"]["estado"] != "ok" and "Capa roja: no medible, no se dibuja" in eje.get_title()
        assert not [l for l in eje.lines if "roja" in l.get_label()]
        for perfil, nombre in (("G", "Capa verde"), ("B", "Capa azul")):
            usadas = _lineas(eje, f"{nombre}: filas usadas")
            d = pagina_mod.datos_del_barrido(r, perfil, ref_gris)
            assert len(usadas) == 1 and np.array_equal(usadas[0].get_xdata(), d["posicion"][d["usada"]]), perfil
            assert np.array_equal(d["posicion"][d["usada"]], (r["perfiles"][perfil]["filas"] - ref_gris) * TAM), perfil

    def test_las_cuatro_capas_dibujan_las_ordenadas_de_cada_capa_y_la_mediana_que_se_reporta(self, resultados, placa_con_repliegue_medible):
        """R1-01: la grafica de las cuatro capas no tenia NINGUNA asercion sobre sus ordenadas ni sobre su linea de mediana (pintar la media donde va la mediana, o invertir el signo de los desfases, solo
        en la rama de varias capas, sobrevivia). Aqui se LEEN de la figura: las ordenadas de las filas usadas de cada capa son `desfases * tam` de `medir_perfil` (exactas), sus abscisas las posiciones respecto
        de la fila de la cuerda mas ancha DEL GRIS, y su mediana punteada es `resumen()['desfase_mm']`; con las peliculas reales, tres placas de PF.0 y la placa de PF.0 que entra por el repliegue."""
        casos = dict(resultados, **{"PF0/repliegue/+1.5": placa_con_repliegue_medible[1]})
        medidas = 0
        for nombre, r in casos.items():
            tam = r["tamano_pixel_mm"]
            eje = _eje()
            pagina_mod.dibujar_barrido_de_filas(eje, r, PERFILES)
            ref = motor.motivos_de_las_filas(r["perfiles"]["gris"]["m"], r["parametros"])["fila_de_referencia"]
            for perfil in PERFILES:
                perfil_r = r["perfiles"][perfil]
                capa = pagina_mod.NOMBRE_DE_PERFIL[perfil]
                usadas, mediana = _lineas(eje, f"{capa}: filas usadas"), _lineas(eje, f"{capa}: mediana (la que se reporta)")
                if perfil_r["estado"] != "ok":
                    assert not usadas and not mediana, (nombre, perfil, "una capa que no se mide no se dibuja")
                    continue
                medidas += 1
                assert len(usadas) == 1 and len(mediana) == 1, (nombre, perfil)
                assert np.array_equal(usadas[0].get_ydata(), perfil_r["desfases"] * tam), (nombre, perfil, "las ordenadas")
                assert np.array_equal(usadas[0].get_xdata(), (perfil_r["filas"] - ref) * tam), (nombre, perfil, "las abscisas")
                reportada = motor.resumen(r, perfil)["desfase_mm"]
                assert mediana[0].get_ydata() == pytest.approx([reportada, reportada], abs=1e-12), (nombre, perfil, "la mediana es la que se reporta")
                assert float(np.mean(perfil_r["desfases"] * tam)) != pytest.approx(reportada, abs=1e-9), (nombre, perfil, "control: la media existe y no es la reportada")
                assert mediana[0].get_linestyle() == ":" and mediana[0].get_color() == usadas[0].get_color(), (nombre, perfil)
                assert usadas[0].get_linestyle() == "-" and usadas[0].get_marker() == "o", (nombre, perfil, "las cuatro capas: puntos unidos por una linea (se sigue cada capa; barrido automatico: AUTO-P672)")
            assert not _lineas(eje, "media") and len(eje.lines) == 2 * sum(r["perfiles"][p]["estado"] == "ok" for p in PERFILES), (nombre, "solo las usadas y su mediana (B4-D3)")
        assert medidas >= 12, f"el censo ve pocas capas medibles ({medidas}): la prueba esta ciega"

    def test_sin_escala_las_cuatro_capas_se_dibujan_y_se_rotulan_en_pixeles(self, resultados):
        """R1-03: «sin escala» solo estaba probado para un perfil: las cuatro capas juntas rotulaban en mm un dato que nadie puede interpretar (resolucion «otra»)."""
        for nombre in ("braqui_00", "EPSON009"):
            r = dict(resultados[nombre], tamano_pixel_mm=None)
            eje = _eje()
            pagina_mod.dibujar_barrido_de_filas(eje, r, PERFILES)
            assert eje.get_xlabel() == "posición de la fila respecto de la cuerda más ancha del gris [px]" and eje.get_ylabel() == "desfase [px]", nombre
            ref = motor.motivos_de_las_filas(r["perfiles"]["gris"]["m"], r["parametros"])["fila_de_referencia"]
            medidas = 0
            for perfil in PERFILES:
                perfil_r = r["perfiles"][perfil]
                if perfil_r["estado"] != "ok":
                    continue
                medidas += 1
                capa = pagina_mod.NOMBRE_DE_PERFIL[perfil]
                (usadas,), (mediana,) = _lineas(eje, f"{capa}: filas usadas"), _lineas(eje, f"{capa}: mediana (la que se reporta)")
                assert np.array_equal(usadas.get_ydata(), perfil_r["desfases"]), (nombre, perfil, "en pixeles, sin multiplicar por ninguna escala")
                assert np.array_equal(usadas.get_xdata(), (perfil_r["filas"] - ref).astype(float)), (nombre, perfil)
                assert mediana.get_ydata() == pytest.approx([perfil_r["desfase_px"]] * 2, abs=1e-12), (nombre, perfil)
            assert medidas >= 3, nombre

    def test_sin_filas_que_no_entran_no_se_dibuja_su_linea_ni_su_entrada_de_la_leyenda(self):
        """Barrido automatico (AUTO-P670): si TODAS las filas con meseta entran, no hay filas que no entran que dibujar (ni una linea vacia con su entrada en la leyenda). Las peliculas reales siempre tienen
        alguna: hace falta un perfil armado a mano."""
        eje = _eje()
        r = _resultado_falso([100] * 12)
        assert motor.motivos_de_las_filas(r["perfiles"]["gris"]["m"], r["parametros"])["usada"].all(), "compuerta: todas las filas con meseta entran"
        pagina_mod.dibujar_barrido_de_filas(eje, r, ("gris",))
        assert not _lineas(eje, "filas con meseta que no entran")
        assert [t.get_text() for t in eje.get_legend().get_texts()] == ["filas usadas", "mediana (la que se reporta)", "media"]

    def test_la_referencia_de_las_cuatro_capas_es_la_cuerda_mas_ancha_del_gris_aunque_sea_la_primera_fila_y_sin_gris_cada_capa_usa_la_suya(self):
        """Barrido automatico (AUTO-P657): la fila de referencia del gris vale -1 cuando no hay meseta en ninguna fila (sin referencia: cada capa usa la suya) y la PRIMERA fila (0) es una referencia valida."""
        def con_capa_roja(anchos_gris, anchos_roja, gris_mide=True):
            r = _resultado_falso(anchos_gris)
            r["perfiles"]["R"] = dict(r["perfiles"]["gris"], m=_m(anchos_roja))
            if not gris_mide:
                r["perfiles"]["gris"] = dict(r["perfiles"]["gris"], estado="no medible: sin meseta")
            return r
        roja = [60] * 5 + [100] + [60] * 6                                    # su cuerda mas ancha es la fila 5; con el repliegue entran sus 12 filas
        # la cuerda mas ancha del gris es la fila 0: las posiciones de la roja se miden desde la fila 0, no desde la 5 de la roja
        r = con_capa_roja([100] + [90] * 11, roja)
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r, ("gris", "R"))
        (en_la_roja,) = _lineas(eje, "Capa roja: filas usadas")
        assert np.array_equal(en_la_roja.get_xdata(), np.arange(12) * TAM), "la fila 0 es una referencia valida (la del gris)"
        # sin ninguna meseta en el gris no hay referencia del gris (-1): la roja se mide desde SU cuerda mas ancha, no desde una fila inexistente
        r = con_capa_roja([0] * 12, roja, gris_mide=False)
        assert motor.motivos_de_las_filas(r["perfiles"]["gris"]["m"], r["parametros"])["fila_de_referencia"] == -1, "compuerta: el gris no tiene meseta"
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r, ("gris", "R"))
        (en_la_roja,) = _lineas(eje, "Capa roja: filas usadas")
        assert np.array_equal(en_la_roja.get_xdata(), (np.arange(12) - 5) * TAM), "sin referencia del gris, la de la propia capa (su cuerda mas ancha)"

    def test_sin_escala_se_dibuja_y_se_rotula_en_pixeles(self, resultados):
        r = dict(resultados["braqui_00"], tamano_pixel_mm=None)
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r, ("gris",))
        assert "[px]" in eje.get_xlabel() and eje.get_ylabel() == "desfase [px]"
        d = pagina_mod.datos_del_barrido(r, "gris")
        assert d["unidad"] == "px" and np.array_equal(d["desfase"][d["usada"]], r["perfiles"]["gris"]["desfases"])


def _pelicula_en_la_pagina(pagina, dialogos, tmp_path, nombre):
    """La pelicula real `nombre` con los clics del fisico, analizada por la PAGINA REAL (sus perfiles se miden): lo que `_mostrar` dibuja en las dos figuras. El gris se mide siempre; EPSON009 mide ademas sus tres
    capas y braqui_00 no mide la roja (por eso se prueban las dos). Devuelve el resultado que la pagina muestra."""
    datos, clics = PELICULAS_REALES[nombre]
    ruta = tmp_path / f"{nombre}.jpeg"
    ruta.write_bytes(datos)
    _analizada(pagina, dialogos, str(ruta), [tuple(c) for c in clics])
    r = pagina._resultado
    medibles = [p for p in PERFILES if r["perfiles"][p]["estado"] == "ok"]
    assert medibles == (list(PERFILES) if nombre == "EPSON009" else ["gris", "G", "B"]), f"compuerta: los perfiles que se miden de {nombre} ({medibles})"
    return r


class TestLaPaginaRealDibujaLosBarridos:
    """R2P-01, R2P-02 y R2P-03 (ronda 2). Las pruebas de `dibujar_barrido_de_filas` la llaman con los perfiles que ELLAS eligen sobre una figura suelta: ninguna fijaba que la PAGINA se los pase bien (quitar «gris»
    de la tupla de `_mostrar` dejaba verdes las 278 pruebas de B.4, B.1 y PI.4) ni de que color pinta cada capa. Aqui se mira la figura real de cada pestaña despues de analizar por la pagina (con la pelicula que
    mide sus cuatro capas y con la que no mide la roja), con oraculos que no usan la API nueva de B.4 (`filas_utiles`, `resumen`, los datos del resultado) y con los colores que la pagina declara (`TINTA`,
    `COLOR_CAPA`) y los del perfil de la MISMA figura."""

    @pytest.mark.parametrize("pelicula", ("EPSON009", "braqui_00"))
    def test_la_pestana_del_gris_dibuja_el_barrido_del_perfil_de_grises_con_todo_lo_que_pide_el_plan(self, pagina, dialogos, tmp_path, pelicula):
        r = _pelicula_en_la_pagina(pagina, dialogos, tmp_path, pelicula)
        gris, tam = r["perfiles"]["gris"], r["tamano_pixel_mm"]
        eje = pagina._fig_gris.axes[-1]
        assert eje.get_title().startswith("Barrido: el desfase de cada fila"), eje.get_title()
        assert sorted(l.get_label() for l in eje.lines) == sorted(["filas con meseta que no entran", "filas usadas", "mediana (la que se reporta)", "media"])
        ref = int(np.argmax(motor.filas_utiles(gris["m"], r["parametros"])[1]))
        (usadas,) = _lineas(eje, "filas usadas")
        assert np.array_equal(usadas.get_ydata(), gris["desfases"] * tam), "las ordenadas son los desfases del GRIS (no los de otra capa)"
        assert np.array_equal(usadas.get_xdata(), (gris["filas"] - ref) * tam)
        ancho = np.where(gris["m"]["inicio"] >= 0, gris["m"]["fin"] - gris["m"]["inicio"] + 1, 0)
        (fuera,) = _lineas(eje, "filas con meseta que no entran")
        assert len(fuera.get_xdata()) == int((ancho > 0).sum()) - len(gris["filas"]) > 0, "las filas CON meseta que no entran"
        (mediana,), (media,) = _lineas(eje, "mediana (la que se reporta)"), _lineas(eje, "media")
        assert mediana.get_ydata() == pytest.approx([motor.resumen(r, "gris")["desfase_mm"]] * 2, abs=1e-12)
        assert media.get_ydata() == pytest.approx([float(np.mean(gris["desfases"] * tam))] * 2, abs=1e-12)
        assert eje.get_xlabel() == "posición de la fila respecto de la cuerda más ancha [mm]"

    @pytest.mark.parametrize("pelicula", ("EPSON009", "braqui_00"))
    def test_la_pestana_de_las_capas_dibuja_las_cuatro_capas_juntas_con_la_referencia_del_gris(self, pagina, dialogos, tmp_path, pelicula):
        """R2P-01: la tupla `("gris", "R", "G", "B")` de `_mostrar` no la fijaba ninguna prueba: sin «gris» la figura perdia el perfil de grises y la fila de referencia de las demas capas pasaba a ser la de
        la roja, con el rotulo («respecto de la cuerda mas ancha del gris») intacto. La figura dibuja el perfil de grises MAS una capa por cada capa que se mide, y las abscisas de cada una (la verde y la azul de
        braqui_00, las tres de EPSON009) son (fila usada - fila de la cuerda mas ancha DEL GRIS) * tam, con `filas_utiles` y `resumen` de antes de B.4."""
        r = _pelicula_en_la_pagina(pagina, dialogos, tmp_path, pelicula)
        tam = r["tamano_pixel_mm"]
        medibles = [p for p in PERFILES if r["perfiles"][p]["estado"] == "ok"]
        eje = pagina._fig_rgb.axes[-1]
        assert eje.get_title().startswith("Barrido de las cuatro capas"), eje.get_title()
        assert eje.get_xlabel() == "posición de la fila respecto de la cuerda más ancha del gris [mm]"
        ref = int(np.argmax(motor.filas_utiles(r["perfiles"]["gris"]["m"], r["parametros"])[1]))
        propia = int(np.argmax(motor.filas_utiles(r["perfiles"][medibles[1]]["m"], r["parametros"])[1]))           # la referencia que quedaria sin el perfil de grises: la de la primera capa de color
        assert ref != propia, "compuerta: con la referencia de la primera capa de color (sin el gris) las abscisas serian otras"
        for perfil in PERFILES:
            capa = pagina_mod.NOMBRE_DE_PERFIL[perfil]
            usadas, mediana = (_lineas(eje, f"{capa}: {que}") for que in ("filas usadas", "mediana (la que se reporta)"))
            if perfil not in medibles:
                assert not usadas and not mediana and f"{capa}: no medible, no se dibuja" in eje.get_title(), (perfil, "una capa que no se mide no se dibuja y el titulo lo dice")
                continue
            assert len(usadas) == len(mediana) == 1, (perfil, "cada capa que se mide, el perfil de grises incluido, dibuja sus filas usadas y su mediana")
            perfil_r = r["perfiles"][perfil]
            assert np.array_equal(usadas[0].get_ydata(), perfil_r["desfases"] * tam), perfil
            assert np.array_equal(usadas[0].get_xdata(), (perfil_r["filas"] - ref) * tam), (perfil, "la referencia de las cuatro es la cuerda mas ancha DEL GRIS")
            assert mediana[0].get_ydata() == pytest.approx([motor.resumen(r, perfil)["desfase_mm"]] * 2, abs=1e-12), perfil
        assert len(eje.lines) == 2 * len(medibles)
        assert [t.get_text() for t in eje.get_legend().get_texts()] == [pagina_mod.NOMBRE_DE_PERFIL[p] for p in medibles] + ["mediana (la que se reporta)"]

    @pytest.mark.parametrize("pelicula", ("EPSON009", "braqui_00"))
    def test_cada_capa_del_barrido_de_las_cuatro_capas_lleva_el_color_de_su_perfil(self, pagina, dialogos, tmp_path, pelicula):
        """R2P-02: `color = TINTA` para todas las capas pasaba las 278 pruebas y la leyenda de esa grafica identifica cada capa SOLO por su color (la prueba de la leyenda comparaba los manejadores con las lineas
        que ella misma leia de la figura). Aqui, para cada capa que se mide, el color de sus filas usadas y de su mediana es el que la pagina declara para ella (TINTA para el gris, `COLOR_CAPA[capa]` para R, G y B),
        los cuatro declarados son distintos entre si, es el mismo con que se dibuja SU perfil en la misma figura (otra referencia, que no es la constante) y es lo que es: la capa roja es rojiza, la verde verdosa
        y la azul azulada; y la leyenda identifica cada capa con ese color."""
        r = _pelicula_en_la_pagina(pagina, dialogos, tmp_path, pelicula)
        medibles = [p for p in PERFILES if r["perfiles"][p]["estado"] == "ok"]
        esperados = {"gris": pagina_mod.TINTA, **pagina_mod.COLOR_CAPA}
        assert len({to_rgb(c) for c in esperados.values()}) == 4, "los cuatro colores que la pagina declara son distintos entre si"
        ejes = pagina._fig_rgb.axes
        eje = ejes[-1]
        en_su_perfil = {"gris": pagina._fig_gris.axes[1], "R": ejes[0], "G": ejes[1], "B": ejes[2]}
        for perfil in medibles:
            capa = pagina_mod.NOMBRE_DE_PERFIL[perfil]
            colores = set()
            for que in ("filas usadas", "mediana (la que se reporta)"):
                lineas = _lineas(eje, f"{capa}: {que}")
                assert len(lineas) == 1, (perfil, que)
                colores.add(lineas[0].get_color())
            assert colores == {esperados[perfil]}, (perfil, colores, "el color que la pagina declara para esa capa (TINTA o COLOR_CAPA)")
            assert esperados[perfil] == _linea_del_perfil(en_su_perfil[perfil]).get_color(), (perfil, "el mismo color con que se dibuja su perfil en la misma figura")
            if perfil == "gris":
                assert not any(_predomina(esperados[perfil], canal) for canal in range(3)), "el perfil de grises es neutro"
            else:
                assert _predomina(esperados[perfil], "RGB".index(perfil)), (perfil, "la capa tiene el color de su nombre")
        manejadores = getattr(eje.get_legend(), "legend_handles", None) or eje.get_legend().legendHandles
        assert [h.get_color() for h in manejadores][:len(medibles)] == [esperados[p] for p in medibles], "la leyenda identifica cada capa por su color"

    @pytest.mark.parametrize("pelicula", ("EPSON009", "braqui_00"))
    def test_las_filas_que_no_entran_se_dibujan_en_un_gris_claro(self, pagina, dialogos, tmp_path, pelicula):
        """R2P-03: el plan pide las filas con meseta que no entran «en gris claro» y la prueba las comparaba con la propia constante de la pagina: pasarla a negro dejaba verdes 278 pruebas. «Gris claro» es
        aqui una PROPIEDAD del color: todos los canales altos, casi sin saturacion y mas claro que la tinta y que cada capa (con lo que se dibuja lo demas) y que las filas usadas."""
        _pelicula_en_la_pagina(pagina, dialogos, tmp_path, pelicula)
        eje = pagina._fig_gris.axes[-1]
        fuera, usadas = _lineas(eje, "filas con meseta que no entran"), _lineas(eje, "filas usadas")
        assert len(fuera) == 1 and len(usadas) == 1, "el barrido del gris dibuja las filas usadas y, aparte, las que no entran"
        color = fuera[0].get_color()
        assert _es_gris_claro(color, COLORES_DE_LA_PAGINA), f"no es un gris claro (ni mas claro que la tinta y que cada capa): {color}"
        assert _luminosidad(color) > _luminosidad(usadas[0].get_color()) + 0.5, "mucho mas claro que las filas usadas"

    def test_el_detector_de_gris_claro_distingue_un_gris_claro_de_lo_que_no_lo_es(self):
        """Trampa 8: las propiedades de color de arriba tienen que caer con lo que no es un gris claro y pasar con el de la pagina, cada clausula por separado: los canales altos, la saturacion y la claridad
        frente a los colores con que se dibuja lo demas."""
        contra = COLORES_DE_LA_PAGINA
        assert _es_gris_claro("#c4c2ba", contra) and _es_gris_claro("#d0d0d0", contra) and _es_gris_claro("#ffffff", contra)           # el de la pagina y dos mas claros
        assert not any(_es_gris_claro(c, contra) for c in ("#000000", "#0b0b0b"))                                                       # el negro y la tinta
        assert not any(_es_gris_claro(c, contra) for c in ("#808080", "#a0a0a0"))                                                       # un gris medio y uno medio claro: canales por debajo de 0.70
        assert not any(_es_gris_claro(c, ()) for c in ("#ff9999", "#99bbff", "#ffd0d0", "#d0e0ff"))                                      # claros pero con color: la saturacion, sin comparar con nadie
        assert not _es_gris_claro("#d0d0d0", contra + ("#f0f0f0",)), "un gris claro no basta si alguno de los otros colores de la pagina es aun mas claro"
        assert _predomina("#e34948", 0) and _predomina("#008300", 1) and _predomina("#2a78d6", 2) and not _predomina("#0b0b0b", 0) and not _predomina("#e34948", 1)


class TestLosDatosDelBarridoLeenLosParametrosConQueSeMidio:
    """R2P-04: `datos_del_barrido` (de donde sale lo que la grafica dibuja como usado, su mediana y su media) debe leer los parametros con que se MIDIO el resultado (`resultado["parametros"]`, que se guardan con cada
    analisis), no los de omision del motor: leer `motor.PARAMETROS` pasaba las 278 pruebas porque todo registro se mide hoy con los de omision. Es la clase que R1-07 cerro para la frase de `texto_de_la_regla`.
    Aqui se mide DE VERDAD con otros parametros (el servicio acepta los suyos) y la grafica tiene que dibujar como usadas exactamente las filas que el motor uso."""
    # los tres parametros que eligen las filas (no `hueco_max`: ese mide la meseta de cada fila); el primero es el caso del revisor: 116 filas en el gris de braqui_00 con ellos y 72 con los de omision
    CAMBIOS = (pytest.param({"fraccion_central": 0.5, "minimo_filas": 25}, 116, id="fraccion_central=0.5-minimo_filas=25"),
               pytest.param({"fraccion_central": 0.95}, None, id="fraccion_central=0.95"),
               pytest.param({"fraccion_central": 0.6, "fraccion_minima": 0.5}, None, id="fraccion_central=0.6-fraccion_minima=0.5"))

    @pytest.mark.parametrize("cambios,usadas_del_gris", CAMBIOS)
    def test_lo_que_se_dibuja_como_usado_es_lo_que_el_motor_uso_con_los_parametros_con_que_se_midio(self, resultados, cambios, usadas_del_gris):
        base = resultados["braqui_00"]
        r = svc.analizar_imagen(BRAQUI_00, CLICS_PLACA_REAL, cambios)
        assert all(r["parametros"][k] == v for k, v in cambios.items())
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r, PERFILES)
        if usadas_del_gris is not None:
            assert len(r["perfiles"]["gris"]["filas"]) == usadas_del_gris != len(base["perfiles"]["gris"]["filas"]), "compuerta: el caso medido por el revisor (116 filas con estos parametros, 72 con los de omision)"
            (del_gris,) = _lineas(eje, "Perfil de grises: filas usadas")
            assert len(del_gris.get_xdata()) == usadas_del_gris, "la figura dibuja las 116 filas que el motor uso con esos parametros y no las 72 de los parametros de omision"
        distintos = 0
        for perfil in PERFILES:
            perfil_r = r["perfiles"][perfil]
            d = pagina_mod.datos_del_barrido(r, perfil)
            assert np.array_equal(d["filas"][d["usada"]], perfil_r["filas"]), (cambios, perfil, "las filas usadas son las que el motor uso con ESOS parametros")
            distintos += not np.array_equal(perfil_r["filas"], base["perfiles"][perfil]["filas"])
            if perfil_r["estado"] == "ok":
                (usadas,) = _lineas(eje, f"{pagina_mod.NOMBRE_DE_PERFIL[perfil]}: filas usadas")
                assert len(usadas.get_xdata()) == len(perfil_r["filas"]), (cambios, perfil, "la figura dibuja esas filas")
        assert distintos >= 3, f"compuerta: con {cambios} la regla elige otras filas que con los parametros de omision (cambian en {distintos} perfiles)"


class TestLaLineaDeLaReglaRelajada:
    def test_con_el_repliegue_forzado_la_linea_lo_dice_con_el_numero_de_filas(self, placa_chica):
        _, r = placa_chica
        d = motor.motivos_de_las_filas(r["perfiles"]["gris"]["m"], r["parametros"])
        assert d["repliegue"] is True, "compuerta: la placa de mancha chica fuerza el repliegue"
        n = d["motivos"].count(motor.MOTIVO_USADA_POR_REPLIEGUE)
        assert n > 0
        assert pagina_mod.texto_de_la_regla(r, "gris") == f"se usaron {n} filas con menos del 80 % porque quedaban menos de 10"

    def test_con_un_hueco_puenteado_la_linea_lo_dice(self, resultados):
        r = resultados["braqui_00"]
        n = motor.motivos_de_las_filas(r["perfiles"]["R"]["m"], r["parametros"])["motivos"].count(motor.MOTIVO_USADA_POR_HUECO)
        assert n > 0, "compuerta: la capa roja de braqui_00 entra por huecos puenteados"
        assert pagina_mod.texto_de_la_regla(r, "R") == f"{n} filas entraron por un hueco puenteado"

    def test_sin_relajacion_no_dice_nada(self, resultados):
        for nombre, r in resultados.items():
            for perfil in PERFILES:
                motivos = motor.motivos_de_las_filas(r["perfiles"][perfil]["m"], r["parametros"])["motivos"]
                relajada = motor.MOTIVO_USADA_POR_REPLIEGUE in motivos or motor.MOTIVO_USADA_POR_HUECO in motivos
                assert (pagina_mod.texto_de_la_regla(r, perfil) != "") == relajada, (nombre, perfil)

    def test_el_singular_y_el_plural_y_los_dos_casos_juntos_a_mano(self):
        def falso(anchos):
            return {"perfiles": {"gris": {"m": _m(anchos)}}, "parametros": P0}
        assert pagina_mod.texto_de_la_regla(falso([100] * 8 + [50] + [100] * 8), "gris") == "1 fila entró por un hueco puenteado"
        assert pagina_mod.texto_de_la_regla(falso([100] * 8 + [50] * 3 + [100] * 8), "gris") == "3 filas entraron por un hueco puenteado"
        assert pagina_mod.texto_de_la_regla(falso([40] + [100] * 9 + [0] * 3), "gris") == "se usó 1 fila con menos del 80 % porque quedaban menos de 10"
        assert pagina_mod.texto_de_la_regla(falso([100] * 12), "gris") == ""

    def test_la_frase_no_lleva_simbolos_de_correcto_o_incorrecto(self, placa_chica, resultados):
        simbolos = set("✓✔✗✘✅❌⚠")
        for r in (placa_chica[1], resultados["braqui_00"]):
            for perfil in PERFILES:
                assert not (set(pagina_mod.texto_de_la_regla(r, perfil)) & simbolos)

    def test_la_pagina_real_con_un_repliegue_medible_dice_el_repliegue_en_la_grafica_y_lo_calla_sin_el(self, pagina, dialogos, placa_con_repliegue_medible, archivo_braqui, tmp_path):
        """R2P-05: lo que la pagina DICE se lee de la figura con un oraculo que no usa la API nueva (el numero de filas sale de `filas_utiles` y su ancho): contra HEAD, que no dice nada, cae por la aserción
        sobre el titulo de la grafica y no por un `AttributeError` al llamar a `texto_de_la_regla`."""
        p, r = placa_con_repliegue_medible
        assert r["perfiles"]["gris"]["estado"] == "ok", "compuerta: el gris de la placa se mide"
        ruta = tmp_path / "placa_repliegue.png"
        ruta.write_bytes(p.datos)
        _analizada(pagina, dialogos, str(ruta), [tuple(c) for c in p.clics])
        rr = pagina._resultado
        n_gris, n_verde = _filas_con_menos_de_la_fraccion(rr, "gris"), _filas_con_menos_de_la_fraccion(rr, "G")
        assert n_gris > 3 and n_verde > 3 and rr["perfiles"]["G"]["estado"] == "ok", "compuerta: mas filas cortas de las que un hueco puenteado (3) puede explicar: el repliegue"
        fraccion, minimo = round(100 * rr["parametros"]["fraccion_central"]), rr["parametros"]["minimo_filas"]          # las cifras de la frase son las de los parametros con que se midio (80 y 10 por omision)
        esperada = f"se usaron {n_gris} filas con menos del {fraccion} % porque quedaban menos de {minimo}"
        assert pagina._fig_gris.axes[-1].get_title().split("\n") == ["Barrido: el desfase de cada fila", esperada]
        titulo = pagina._fig_rgb.axes[-1].get_title()
        assert titulo.startswith("Barrido de las cuatro capas")
        assert f"Capa verde: se usaron {n_verde} filas con menos del {fraccion} % porque quedaban menos de {minimo}" in titulo
        assert pagina_mod.texto_de_la_regla(rr, "gris") == esperada            # la funcion dice lo mismo que la figura
        # sin relajacion en el gris (braqui_00 con los clics del fisico) la grafica no lleva ninguna frase de la regla
        pagina.boton_limpiar.click()
        _analizada(pagina, dialogos, archivo_braqui)
        assert pagina._fig_gris.axes[-1].get_title() == "Barrido: el desfase de cada fila"
        assert pagina_mod.texto_de_la_regla(pagina._resultado, "gris") == ""

    def test_la_pagina_real_con_epson009_dice_el_hueco_de_la_capa_roja_que_si_se_dibuja_en_el_titulo_de_las_cuatro_capas(self, pagina, dialogos, tmp_path):
        """R1-02: la prueba que habia (con braqui_00) afirmaba en su nombre un hueco de la capa verde o azul que no existe: la unica frase de hueco de braqui_00 es la de la capa ROJA, que no se mide y no se
        dibuja. EPSON009 SI mide su capa roja y esa capa entra por un hueco puenteado: la frase llega al titulo de la figura de las cuatro capas, con el nombre de la capa."""
        ruta = tmp_path / "EPSON009.jpeg"
        ruta.write_bytes(EPSON009)
        _analizada(pagina, dialogos, str(ruta), [tuple(c) for c in CLICS_EPSON009])
        r = pagina._resultado
        assert r["perfiles"]["R"]["estado"] == "ok", "compuerta: la capa roja de EPSON009 se mide, asi que se dibuja"
        # R2P-05: lo que la figura dice, con un oraculo sin la API nueva (las filas usadas con menos de la fraccion central son las del hueco cuando no hay repliegue)
        n = _filas_con_menos_de_la_fraccion(r, "R")
        assert n >= 1, "compuerta: la capa roja de EPSON009 entra por un hueco puenteado"
        barrido = pagina._fig_rgb.axes[-1]
        titulo = barrido.get_title()
        assert titulo.startswith("Barrido de las cuatro capas"), titulo
        assert f"Capa roja: {n} {'fila entró' if n == 1 else 'filas entraron'} por un hueco puenteado" in titulo, titulo
        assert "porque quedaban menos de" not in titulo, "compuerta: ninguna capa de EPSON009 entra por el repliegue (n seria las filas del repliegue, no las del hueco)"
        assert _lineas(barrido, "Capa roja: filas usadas"), "la capa que dice el hueco es una capa DIBUJADA"
        frase = pagina_mod.texto_de_la_regla(r, "R")                          # la funcion dice lo mismo que la figura
        assert re.fullmatch(r"\d+ filas? entr(ó|aron) por un hueco puenteado", frase) and f"Capa roja: {frase}" in titulo

    def test_la_pagina_real_con_braqui_00_no_dice_el_hueco_de_la_capa_roja_porque_no_se_mide_ni_se_dibuja(self, pagina, dialogos, archivo_braqui):
        _analizada(pagina, dialogos, archivo_braqui)
        r = pagina._resultado
        barrido = pagina._fig_rgb.axes[-1]                                     # R2P-05: primero lo que la figura dice (contra HEAD cae aqui), despues las compuertas con la API nueva
        assert "Capa roja: no medible, no se dibuja" in barrido.get_title() and "hueco" not in barrido.get_title()
        assert not _lineas(barrido, "Capa roja: filas usadas")
        assert r["perfiles"]["R"]["estado"] != "ok" and "hueco puenteado" in pagina_mod.texto_de_la_regla(r, "R"), "compuerta: el motor SI vio un hueco en la capa roja, que no se mide"

    def test_un_repliegue_que_solo_suma_filas_de_otro_bloque_tambien_lo_dice(self):
        """R1-05 (B4-D7): si el bloque central quedaba con menos de 10 filas y el repliegue suma SOLO filas de otro bloque con cuerdas de 80 % o mas, la regla se relajo (el conjunto candidato paso del bloque
        central a toda la imagen) y antes no se decia: ninguna fila quedaba rotulada «por el repliegue» (B4-D6) y la frase salia vacia."""
        def frase(anchos, parametros=None):
            return pagina_mod.texto_de_la_regla(_resultado_falso(anchos, parametros), "gris")
        assert frase([50] * 6 + [0] * 4 + [50] * 6) == "el barrido tomó 6 filas de fuera del bloque central porque en él quedaban menos de 10"
        assert frase([100] * 5 + [0] * 10 + [90] * 6) == "el barrido tomó 6 filas de fuera del bloque central porque en él quedaban menos de 10"
        assert frase([100] * 9 + [0] * 5 + [100]) == "el barrido tomó 1 fila de fuera del bloque central porque en él quedaban menos de 10"
        # donde la frase ya salia (hay filas con menos del 80 %), sale esa y solo esa
        assert frase([40] + [100] * 9 + [0] * 3) == "se usó 1 fila con menos del 80 % porque quedaban menos de 10"
        assert frase([40] * 6 + [100] * 5 + [40] * 6 + [20] * 3) == "se usaron 12 filas con menos del 80 % porque quedaban menos de 10"
        # sin nada de otro bloque, nada que decir (un perfil con menos de diez filas no es medible: la pagina no lo dibuja)
        assert frase([100] * 9) == "" and frase([100] * 12) == ""

    def test_la_grafica_dice_el_repliegue_de_otro_bloque_en_el_titulo_de_un_perfil_y_de_las_cuatro_capas(self):
        frase = "el barrido tomó 6 filas de fuera del bloque central porque en él quedaban menos de 10"
        r = _resultado_falso([50] * 6 + [0] * 4 + [50] * 6)
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r, ("gris",))
        assert eje.get_title().split("\n")[1:] == [frase]
        for capa in "RGB":
            r["perfiles"][capa] = dict(r["perfiles"]["gris"])
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r, PERFILES)
        titulo = eje.get_title()
        assert all(f"{pagina_mod.NOMBRE_DE_PERFIL[p]}: {frase}" in titulo for p in PERFILES), titulo

    def test_la_frase_lee_las_fracciones_y_el_minimo_con_que_se_midio(self):
        """R1-07: las cifras de la frase salen de los parametros con que se midio, no de numeros escritos."""
        def frase(anchos, **cambios):
            return pagina_mod.texto_de_la_regla(_resultado_falso(anchos, dict(P0, **cambios)), "gris")
        assert frase([40] + [100] * 9 + [0] * 3) == "se usó 1 fila con menos del 80 % porque quedaban menos de 10"
        assert frase([60] + [100] * 9 + [0] * 3, fraccion_central=0.7, fraccion_minima=0.2) == "se usó 1 fila con menos del 70 % porque quedaban menos de 10"
        assert frase([40] + [100] * 9 + [0] * 3, minimo_filas=12) == "se usó 1 fila con menos del 80 % porque quedaban menos de 12"
        assert frase([50] * 6 + [0] * 4 + [50] * 6, minimo_filas=12) == "el barrido tomó 6 filas de fuera del bloque central porque en él quedaban menos de 12"
        # una cuerda al 75 % es corta con el 80 % (y el bloque queda en 9 filas) y ancha con el 70 % (el bloque llega a 10): la frase y la clasificacion usan la misma fraccion
        assert frase([75] + [100] * 9 + [0] * 3) == "se usó 1 fila con menos del 80 % porque quedaban menos de 10"
        assert frase([75] + [100] * 9 + [0] * 3, fraccion_central=0.7) == ""


class TestLaLeyendaDelBarrido:
    """R1-08: la leyenda de la grafica de las cuatro capas (`loc="upper left"`, dos columnas, dentro de los ejes) tapaba 16 de 215 puntos usados en braqui_00 y 28 de 161 en EPSON009 (0 en el gris): los
    datos llenan el eje y ningun rincon esta libre. La leyenda va FUERA de los ejes, a su derecha (la disposicion le deja el sitio), sin quitarle alto a ningun eje. Las aserciones sobre los limites no ven
    una leyenda que tapa (lo ensenó B.1): se mide la geometria de la figura ya dibujada, y las capturas se miran."""

    @pytest.mark.parametrize("pelicula", ("braqui_00", "EPSON009"))
    @pytest.mark.parametrize("figura,pestana", (("_fig_gris", pagina_mod.PESTANA_GRIS), ("_fig_rgb", pagina_mod.PESTANA_RGB)))
    def test_la_leyenda_va_fuera_de_los_ejes_dentro_de_la_figura_y_no_tapa_ninguna_fila_usada(self, pagina, dialogos, app, tmp_path, pelicula, figura, pestana):
        datos, clics = PELICULAS_REALES[pelicula]
        ruta = tmp_path / f"{pelicula}.jpeg"
        ruta.write_bytes(datos)
        pagina.resize(1500, 1000)
        pagina.show()
        app.processEvents()
        _analizada(pagina, dialogos, str(ruta), [tuple(c) for c in clics])
        pagina.pestanas.setCurrentIndex(pestana)
        app.processEvents()
        figura_ = getattr(pagina, figura)
        eje = figura_.axes[-1]
        assert eje.get_title().startswith("Barrido"), "el ultimo eje de la figura no es el barrido"          # R2P-05: contra HEAD cae aqui (no hay barrido), no por un `NoneType` sin leyenda
        assert eje.get_legend() is not None, "el barrido no tiene leyenda"
        figura_.canvas.draw()
        ejes, caja, hoja = eje.get_window_extent(), eje.get_legend().get_window_extent(), figura_.bbox
        assert caja.x0 >= ejes.x1, "la leyenda esta dentro de los ejes: tapa lo que se dibuja"
        assert caja.x1 <= hoja.x1 + 0.5 and caja.y0 >= hoja.y0 - 0.5 and caja.y1 <= hoja.y1 + 0.5, "la leyenda se sale de la figura (se recortaria)"
        puntos = 0
        for linea in eje.lines:
            if linea.get_label().endswith("filas usadas") or linea.get_label() == "filas usadas":
                xy = eje.transData.transform(np.c_[linea.get_xdata(), linea.get_ydata()])
                puntos += len(xy)
                assert not ((xy[:, 0] >= caja.x0) & (xy[:, 0] <= caja.x1) & (xy[:, 1] >= caja.y0) & (xy[:, 1] <= caja.y1)).any()
        assert puntos > 30, "compuerta: la figura dibuja filas usadas"

    def test_la_leyenda_de_las_cuatro_capas_nombra_cada_capa_dibujada_con_su_color_y_la_mediana(self, resultados):
        r = resultados["EPSON009"]
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r, PERFILES)
        leyenda = eje.get_legend()
        medibles = [p for p in PERFILES if r["perfiles"][p]["estado"] == "ok"]
        assert len(medibles) == 4, "compuerta: las cuatro capas de EPSON009 se miden"
        assert [t.get_text() for t in leyenda.get_texts()] == [pagina_mod.NOMBRE_DE_PERFIL[p] for p in medibles] + ["mediana (la que se reporta)"]
        manejadores = getattr(leyenda, "legend_handles", None) or leyenda.legendHandles
        declarados = {"gris": pagina_mod.TINTA, **pagina_mod.COLOR_CAPA}            # R2P-02: la leyenda se compara con los colores que la pagina declara y no solo con las lineas que esta misma prueba lee de la figura (tautologia)
        colores = [_lineas(eje, f"{pagina_mod.NOMBRE_DE_PERFIL[p]}: filas usadas")[0].get_color() for p in medibles]
        assert [h.get_color() for h in manejadores][:4] == colores == [declarados[p] for p in medibles] and manejadores[4].get_linestyle() == ":"
        r_sin_roja = resultados["braqui_00"]
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, r_sin_roja, PERFILES)
        assert [t.get_text() for t in eje.get_legend().get_texts()] == ["Perfil de grises", "Capa verde", "Capa azul", "mediana (la que se reporta)"], "la capa que no se dibuja no esta en la leyenda"
        eje = _eje()                                                           # barrido automatico (AUTO-P688): con UNA sola capa dibujada la leyenda sigue siendo la de las cuatro juntas
        pagina_mod.dibujar_barrido_de_filas(eje, r_sin_roja, ("gris", "R"))
        leyenda = eje.get_legend()
        assert [t.get_text() for t in leyenda.get_texts()] == ["Perfil de grises", "mediana (la que se reporta)"] and "Capa roja: no medible, no se dibuja" in eje.get_title()
        manejadores = getattr(leyenda, "legend_handles", None) or leyenda.legendHandles
        assert manejadores[0].get_color() == _lineas(eje, "Perfil de grises: filas usadas")[0].get_color() == pagina_mod.TINTA and [h.get_linestyle() for h in manejadores[1:]] == [":"]

    def test_la_leyenda_de_un_perfil_nombra_lo_que_dibuja_y_una_figura_sin_nada_que_leer_no_lleva_leyenda(self, resultados):
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, resultados["braqui_00"], ("gris",))
        assert [t.get_text() for t in eje.get_legend().get_texts()] == ["filas con meseta que no entran", "filas usadas", "mediana (la que se reporta)", "media"]
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, resultados["braqui_00"], ("R",))
        assert eje.get_legend() is not None and [t.get_text() for t in eje.get_legend().get_texts()] == ["filas con meseta (no se mide)"]
        eje = _eje()
        pagina_mod.dibujar_barrido_de_filas(eje, resultados["braqui_00"], ("R", "R"))
        assert eje.get_legend() is None, "dos capas que no se miden: nada que leyendar"


class TestLosEjesDeLasFiguras:
    def test_el_numero_y_el_orden_de_los_ejes_estan_declarados(self, pagina, dialogos, archivo_braqui):
        _analizada(pagina, dialogos, archivo_braqui)                         # R2P-05: primero lo que la pagina dibuja (contra HEAD cae aqui: 2 ejes en el gris), despues las constantes
        assert len(pagina._fig_gris.axes) == 3 and len(pagina._fig_rgb.axes) == 4
        assert pagina._fig_gris.axes[-1].get_title().startswith("Barrido") and pagina._fig_rgb.axes[-1].get_title().startswith("Barrido")
        assert pagina_mod.EJES_DE_LA_PESTANA_DEL_GRIS == ("ventana", "perfil", "barrido")
        assert pagina_mod.EJES_DE_LA_PESTANA_DE_LAS_CAPAS == ("R", "G", "B", "barrido")
        assert len(pagina_mod.ALTOS_DE_LA_PESTANA_DEL_GRIS) == len(pagina_mod.EJES_DE_LA_PESTANA_DEL_GRIS)
        assert len(pagina_mod.ALTOS_DE_LA_PESTANA_DE_LAS_CAPAS) == len(pagina_mod.EJES_DE_LA_PESTANA_DE_LAS_CAPAS)

    def test_el_alto_minimo_del_lienzo_cubre_el_eje_nuevo(self):
        assert pagina_mod.ALTO_MINIMO_DEL_LIENZO["gris"] >= 600 and pagina_mod.ALTO_MINIMO_DEL_LIENZO["rgb"] >= 630


class TestNingunControlCambiaLaRegla:
    PARAMETROS_DE_LA_REGLA = ("fraccion_central", "fraccion_minima", "minimo_filas", "hueco_max")

    def _ambitos(self):
        """{nombre del parametro de la regla: ambitos (funcion o clase mas interna, o el nombre de la asignacion de modulo) donde la pagina lo nombra como texto}."""
        arbol = ast.parse(PAGINA_PY.read_text(encoding="utf-8"))
        encontrados = {}

        def visitar(nodo, ambito):
            if isinstance(nodo, (ast.FunctionDef, ast.ClassDef)):
                ambito = nodo.name
            elif isinstance(nodo, ast.Assign) and ambito == "<modulo>" and isinstance(nodo.targets[0], ast.Name):
                ambito = nodo.targets[0].id
            if isinstance(nodo, ast.Constant) and nodo.value in self.PARAMETROS_DE_LA_REGLA:
                encontrados.setdefault(nodo.value, set()).add(ambito)
            for hijo in ast.iter_child_nodes(nodo):
                visitar(hijo, ambito)
        visitar(arbol, "<modulo>")
        return encontrados

    def test_los_parametros_de_la_regla_solo_se_nombran_para_censarlos_o_para_leerlos(self):
        permitidos = {"TRAZO_DE_PARAMETRO", "texto_de_la_regla"}
        fuera = {k: v - permitidos for k, v in self._ambitos().items() if v - permitidos}
        assert not fuera, f"la pagina nombra parametros de la regla fuera del censo y de la frase: {fuera}"

    def test_la_pagina_real_no_tiene_deslizadores_ni_cajas_de_numero_ni_casillas(self):
        """Los deslizadores son de la PESTANA SINTETICA (la placa), no de la regla: la clase de la pagina real no construye ninguno."""
        arbol = ast.parse(PAGINA_PY.read_text(encoding="utf-8"))
        clase = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == "PosicionInicialBraqui")
        construidos = {n.func.id for n in ast.walk(clase) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert not (construidos & {"QSpinBox", "QDoubleSpinBox", "QSlider", "QCheckBox", "_DeslizadorSinRueda"}), construidos & {"QSpinBox", "QDoubleSpinBox", "QSlider", "QCheckBox"}
        assert not ({d.clave for d in pagina_mod.DESLIZADORES} & set(self.PARAMETROS_DE_LA_REGLA))

    def test_el_detector_ve_un_control_fabricado_sobre_un_parametro_de_la_regla(self, tmp_path, monkeypatch):
        """Trampa 8: el censo cae con un caso fabricado a mano (un parametro de la regla nombrado dentro de una clase de la pagina)."""
        falso = tmp_path / "pagina_falsa.py"
        falso.write_text(PAGINA_PY.read_text(encoding="utf-8") + "\n\nclass Falsa:\n    def construir(self):\n        return 'fraccion_central'\n", encoding="utf-8")
        monkeypatch.setattr(sys.modules[__name__], "PAGINA_PY", falso)
        assert any(v - {"TRAZO_DE_PARAMETRO", "texto_de_la_regla"} for v in self._ambitos().values())
