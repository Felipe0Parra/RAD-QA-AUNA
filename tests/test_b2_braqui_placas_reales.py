"""B.2 (PLAN_ANALISIS_PELICULAS_08-10.md): las placas REALES de la posicion inicial de braquiterapia contra la REFERENCIA INDEPENDIENTE.

En una placa real no hay verdad conocida: lo que se puede pedir es que el motor coincida con un metodo que no es el suyo ni el del cuaderno del fisico. La referencia es morfologia sobre el gris crudo
(`tests/_referencia_independiente_braqui.py`, el guion `med_braqui_referencia_independiente.py` del anexo pasado a modulo auxiliar de pruebas): mascara de «meseta saturada» (gris <= T), apertura que borra la
linea, centro de la mancha en las 31 filas centrales DE LA MANCHA y linea por el centroide de su exceso fuera de la mancha. Se valida primero donde SI hay verdad (las sinteticas) y no importa nada del motor.

  * las cuatro peliculas (EPSON009 con dos juegos de clics, braqui_00.jpeg, EPSON031 -la pagina entera del escaner, con la linea horizontal- y braqui_00.JPG): el gris del motor coincide con la
    referencia a <= 0.05 mm (medido el 14-10: 0.019, 0.021, 0.013, 0.038 y 0.040 mm);
  * braqui_00.jpeg, braqui_00.JPG y EPSON031 son la MISMA pelicula (dos recortes y la pagina): el motor da lo mismo en las tres a 0.02 mm en el gris.
Las pruebas saltan (HI-0) solo si el corpus del fisico no esta: las tres peliculas de `tests/datos/` van en el repositorio y la cuarta (braqui_00.JPG) vive en el corpus.

QUE DEMUESTRA Y QUE NO (ronda 1 de la revision, hallazgo DL-03). El «<= 0.05 mm» vale para la meseta que la referencia ELIGE: toma el umbral T cuya mancha mide el ancho mas cercano a 6.4 mm, que es
el ancho de la cuerda MAS ANCHA que mide el motor (6.2 a 6.5 mm). Son dos estimadores del CENTRO sobre una meseta definida casi igual; no validan la definicion de la meseta, que es una propiedad de la
pelicula (cuanto mas bajo el umbral, mas angosta la mancha). Medido el 14-10 (guion `sensibilidad_T.py` de la revision, repetido en `logs/B2/correccion_r1/`): con otro umbral la diferencia con el motor es
  EPSON009: T = 4 y 8 dan manchas de 3.1 y 3.9 mm (la mitad de la del motor, 5.9 mm en sus 31 filas centrales) y difieren 0.70 y 0.77 mm; solo T = 16 (6.39 mm) es comparable y difiere 0.019 / 0.021 mm;
  braqui_00.jpeg / EPSON031 / braqui_00.JPG: T = 8 (6.56 mm) difiere 0.013 / 0.038 / 0.040 mm y T = 4 (6.01 mm, mas cerca del ancho central del motor, 6.2 a 6.3 mm) difiere 0.072 / 0.067 / 0.088 mm.
Por eso la clase `TestElAcuerdoDependeDeLaMesetaQueLaReferenciaElige` fija LA PREMISA (la meseta elegida es de ancho comparable a la del motor: una regla del ancho que eligiera otra mancha ya no compararia
lo mismo) y el LIMITE CONOCIDO (con cualquier meseta de ancho comparable el motor coincide a <= 0.12 mm: medido 0.088), y `TestLosCriteriosDeLasPlacasRealesDiscriminan` prueba que cada criterio CAE con un
caso malo (Trampa 8). Esta prueba no toca produccion (riesgo NULO).
"""
import ast
import os
from dataclasses import dataclass

import cv2
import numpy as np
import pytest

import _referencia_independiente_braqui as ref
import _verdad_braqui as vb

AQUI = os.path.dirname(os.path.abspath(__file__))
NOMBRES = [p[0] for p in vb.PLACAS_REALES]
# Los umbrales cuya mancha en la referencia es de ancho comparable al de la meseta del motor (medido el 14-10): EPSON009 solo T = 16 (T = 4 y 8 miden 3.1 y 3.9 mm); las tres de braqui T = 4 y 8 (16 mide 8.0 mm).
UMBRALES_COMPARABLES = {"EPSON009 (clics del cuaderno)": {16}, "EPSON009 (clics de la suite)": {16}, "braqui_00.jpeg": {4, 8}, "EPSON031 (pagina entera)": {4, 8}, "braqui_00.JPG (otro recorte)": {4, 8}}


def _ruta(archivo):
    ruta = vb.ruta_de_la_placa_real(archivo)
    if ruta is None or not os.path.isfile(ruta):
        pytest.skip(f"HI-0: la pelicula {archivo} del corpus del fisico no esta")
    return ruta


@dataclass(frozen=True)
class Real:
    """Una placa real medida: lo que dice el motor, la referencia con el umbral que elige su regla y la referencia con cada umbral."""
    medicion: object
    elegida: tuple          # (T elegido, desfase de la referencia en mm)
    por_umbral: dict        # {T: {'desfase_mm', 'ancho_mm', ...} | None}


@pytest.fixture(scope="module")
def mediciones_reales():
    """{nombre: Real} de las placas que existen."""
    out = {}
    for nombre, archivo, clics in vb.PLACAS_REALES:
        ruta = vb.ruta_de_la_placa_real(archivo)
        if ruta is None or not os.path.isfile(ruta):
            continue
        with open(ruta, "rb") as f:
            medicion = vb.medir_bytes(f.read(), clics)
        gris = cv2.imread(ruta, 0)
        clics_ref = [list(c) for c in clics]
        out[nombre] = Real(medicion, ref.elegida_de_la_imagen(gris, clics_ref), ref.referencia_de_la_imagen(gris, clics_ref))
    return out


def _real(nombre, mediciones_reales):
    if nombre not in mediciones_reales:
        _ruta(next(a for n, a, c in vb.PLACAS_REALES if n == nombre))     # salta con el motivo (HI-0)
    return mediciones_reales[nombre]


class TestLaReferenciaIndependiente:
    def test_el_modulo_de_la_referencia_no_importa_el_motor_ni_la_aplicacion(self):
        """No se valida un motor con una copia de si mismo: el modulo solo importa numpy y cv2."""
        with open(os.path.join(AQUI, "_referencia_independiente_braqui.py"), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        importados = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Import):
                importados |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                importados.add((n.module or "").split(".")[0])
        assert importados == {"numpy", "cv2"}, importados

    def test_la_referencia_acierta_donde_hay_verdad(self):
        """Sobre las sinteticas (PNG, ruido) con verdad conocida: en el independiente, con el umbral que elige su regla, a <= 0.03 mm; en el fisico (cuya mancha saturada mide 6.3 mm) el umbral de 16 niveles a <= 0.05 mm."""
        peor = {"independiente": 0.0, "fisico": 0.0}
        for modelo, T_fijo in (("independiente", None), ("fisico", 16)):
            for i, d in enumerate((-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0)):
                placa = vb.placa_de_la_rejilla(modelo, False, "png", d, i)
                gris = cv2.imdecode(np.frombuffer(placa.datos, np.uint8), cv2.IMREAD_GRAYSCALE)
                if T_fijo is None:
                    T, medido = ref.elegida_de_la_imagen(gris, placa.clics)
                    assert T == 16, "en el generador independiente (mancha saturada de ~4 mm) la regla del ancho elige el umbral mas ancho"
                else:
                    medido = ref.referencia_de_la_imagen(gris, placa.clics)[T_fijo]["desfase_mm"]
                peor[modelo] = max(peor[modelo], abs(medido - placa.verdad.desfase_mm))
        assert peor["independiente"] <= 0.03, peor
        assert peor["fisico"] <= 0.05, peor

    def test_la_referencia_distingue_un_desfase_de_otro(self):
        """No vacuidad: la referencia sigue al desfase verdadero (pendiente 1.00 +- 0.02 entre -2 y +2 mm), no devuelve una constante."""
        v, m = [], []
        for i, d in enumerate((-2.0, -1.0, 0.0, 1.0, 2.0)):
            placa = vb.placa_de_la_rejilla("independiente", False, "png", d, i)
            gris = cv2.imdecode(np.frombuffer(placa.datos, np.uint8), cv2.IMREAD_GRAYSCALE)
            v.append(placa.verdad.desfase_mm)
            m.append(ref.elegida_de_la_imagen(gris, placa.clics)[1])
        assert np.polyfit(v, m, 1)[0] == pytest.approx(1.0, abs=0.02)


class TestLasPlacasReales:
    @pytest.mark.parametrize("nombre", NOMBRES)
    def test_el_gris_del_motor_coincide_con_la_referencia_independiente_a_0_05_mm(self, nombre, mediciones_reales):
        """El criterio del plan, con la meseta que elige la regla del ancho de la referencia (ver el docstring del archivo y la clase siguiente: vale para ESA meseta)."""
        real = _real(nombre, mediciones_reales)
        T, desfase_referencia = real.elegida
        gris = real.medicion.medidas["gris"]
        fallos = vb.fallos_contra_la_referencia(nombre, gris.mm, desfase_referencia, T)
        assert not fallos, "\n".join(fallos)
        assert gris.veredicto == "Cumple", "las placas reales de braqui quedan a menos de 0.4 mm de la marca"

    def test_las_cinco_mediciones_estan_hechas_y_ninguna_es_cero_exacto(self, mediciones_reales):
        if len(mediciones_reales) < len(vb.PLACAS_REALES):
            pytest.skip("HI-0: falta una pelicula del corpus del fisico")
        assert set(mediciones_reales) == set(NOMBRES)
        for nombre, real in mediciones_reales.items():
            d = real.elegida[1]
            assert real.medicion.medidas["gris"].mm != 0.0 and d != 0.0 and abs(d) < 0.5

    def test_la_misma_pelicula_recortada_y_en_pagina_entera_da_lo_mismo_a_0_02_mm_en_el_gris(self, mediciones_reales):
        if not all(n in mediciones_reales for n in vb.LA_MISMA_PELICULA):
            pytest.skip("HI-0: falta una pelicula del corpus del fisico")
        valores = {capa: {n: mediciones_reales[n].medicion.medidas[capa].mm for n in vb.LA_MISMA_PELICULA} for capa in vb.DIFERENCIA_ENTRE_RECORTES_MM}
        fallos = vb.fallos_entre_recortes(valores)
        assert not fallos, "\n".join(fallos)


class TestElAcuerdoDependeDeLaMesetaQueLaReferenciaElige:
    """Hallazgo DL-03 de la revision (ronda 1): el acuerdo de 0.05 mm existe para la meseta que la referencia elige; aqui se fija la PREMISA (de ancho comparable a la del motor) y el LIMITE CONOCIDO
    (con cualquier meseta comparable, 0.12 mm) para que una regla del ancho que eligiera otra mancha, o un motor que se aleje de las otras definiciones, no pasen sin que nada lo vea."""

    @pytest.mark.parametrize("nombre", NOMBRES)
    def test_la_meseta_que_elige_la_referencia_es_de_ancho_comparable_a_la_del_motor(self, nombre, mediciones_reales):
        real = _real(nombre, mediciones_reales)
        T = real.elegida[0]
        fallos = vb.fallos_de_la_meseta_comparable(nombre, real.medicion.ancho_meseta_mm, real.por_umbral[T]["ancho_mm"])
        assert not fallos, "\n".join(fallos)

    @pytest.mark.parametrize("nombre", NOMBRES)
    def test_con_cualquier_meseta_de_ancho_comparable_el_motor_coincide_a_0_12_mm(self, nombre, mediciones_reales):
        real = _real(nombre, mediciones_reales)
        ancho = real.medicion.ancho_meseta_mm
        fallos = vb.fallos_con_otras_mesetas(nombre, real.medicion.medidas["gris"].mm, ancho, real.por_umbral)
        assert not fallos, "\n".join(fallos)
        assert set(vb.umbrales_con_meseta_comparable(ancho, real.por_umbral)) == UMBRALES_COMPARABLES[nombre], \
            "los umbrales cuya mancha es comparable a la del motor: EPSON009 solo T = 16; las tres de braqui T = 4 y 8 (no vacuidad: en esas el acuerdo se mide con DOS definiciones de la meseta)"
        assert real.elegida[0] in vb.umbrales_con_meseta_comparable(ancho, real.por_umbral), "el umbral que elige la regla del ancho es uno de los comparables"

    def test_el_ancho_de_la_meseta_del_motor_es_el_de_la_pelicula(self, mediciones_reales):
        """El ancho que se le compara a la referencia sale de las cuerdas del motor (31 filas centrales de su meseta, subpixel) y esta entre 5.8 y 6.4 mm en las cinco mediciones (el de la cuerda mas ancha, 6.2 a 6.5)."""
        if len(mediciones_reales) < len(vb.PLACAS_REALES):
            pytest.skip("HI-0: falta una pelicula del corpus del fisico")
        for nombre, real in mediciones_reales.items():
            assert real.medicion.ancho_meseta_mm is not None and 5.8 <= real.medicion.ancho_meseta_mm <= 6.4, (nombre, real.medicion.ancho_meseta_mm)


class TestLosCriteriosDeLasPlacasRealesDiscriminan:
    """Cada criterio de las placas reales cae con un caso malo y pasa con uno bueno (Trampa 8): hallazgo DL-02 de la revision -- aflojar 10 veces `TOLERANCIA_CONTRA_LA_REFERENCIA_MM` o
    `DIFERENCIA_ENTRE_RECORTES_MM` dejaba todo en verde porque las cinco placas miden 0.013 a 0.040 mm y nada ejercia el criterio con un caso malo. Estas pruebas no necesitan el corpus (no saltan)."""

    def test_las_tolerancias_de_las_placas_reales_son_las_que_fija_el_plan(self):
        assert vb.TOLERANCIA_CONTRA_LA_REFERENCIA_MM == 0.05
        assert vb.DIFERENCIA_ENTRE_RECORTES_MM == {"gris": 0.02, "G": 0.03, "B": 0.03}
        assert vb.ANCHO_COMPARABLE_DE_LA_MESETA_MM == 1.0
        assert vb.TECHO_CON_OTRA_MESETA_MM == 0.12

    def test_el_criterio_contra_la_referencia_cae_con_una_diferencia_de_0_055_mm_o_si_falta_una_medida(self):
        assert not vb.fallos_contra_la_referencia("p", -0.360, -0.405, 8), "0.045 mm: bajo la tolerancia de 0.05"
        assert not vb.fallos_contra_la_referencia("p", -0.405, -0.360, 8), "el signo de la diferencia no importa"
        assert vb.fallos_contra_la_referencia("p", -0.360, -0.415, 8), "0.055 mm pasa la tolerancia de 0.05"
        assert vb.fallos_contra_la_referencia("p", -0.415, -0.360, 8)
        assert vb.fallos_contra_la_referencia("p", None, -0.4, 8), "el motor no mide el gris"
        assert vb.fallos_contra_la_referencia("p", -0.36, None, 8), "la referencia no encontro la mancha"

    def test_el_criterio_entre_recortes_cae_con_0_03_mm_en_el_gris_o_0_04_en_la_verde_o_la_azul_o_si_falta_un_valor(self):
        def valores(**cambios):
            base = {"gris": {"a": -0.360, "b": -0.350, "c": -0.355}, "G": {"a": -0.370, "b": -0.350, "c": -0.360}, "B": {"a": -0.340, "b": -0.360, "c": -0.350}}      # dispersiones de 0.010, 0.020 y 0.020 mm
            base.update(cambios)
            return base
        assert not vb.fallos_entre_recortes(valores())
        assert not vb.fallos_entre_recortes(valores(gris={"a": -0.360, "b": -0.341, "c": -0.350})), "0.019 mm en el gris: bajo +-0.02"
        assert vb.fallos_entre_recortes(valores(gris={"a": -0.360, "b": -0.330, "c": -0.350})), "0.03 mm en el gris pasa +-0.02"
        assert not vb.fallos_entre_recortes(valores(G={"a": -0.370, "b": -0.341, "c": -0.360})), "0.029 mm en la verde: bajo +-0.03"
        assert vb.fallos_entre_recortes(valores(G={"a": -0.390, "b": -0.350, "c": -0.360})), "0.04 mm en la verde pasa +-0.03"
        assert vb.fallos_entre_recortes(valores(B={"a": -0.320, "b": -0.360, "c": -0.350})), "0.04 mm en la azul pasa +-0.03"
        assert vb.fallos_entre_recortes(valores(gris={"a": -0.360, "b": None, "c": -0.350})), "una de las tres no se mide"
        assert vb.fallos_entre_recortes({k: v for k, v in valores().items() if k != "G"}), "una capa sin valores no se puede dar por buena"
        assert vb.fallos_entre_recortes(valores(gris={"a": -0.360})), "con una sola placa no hay nada que comparar"

    def test_el_criterio_de_la_meseta_comparable_cae_si_los_anchos_difieren_mas_de_un_milimetro_o_falta_uno(self):
        assert not vb.fallos_de_la_meseta_comparable("p", 6.17, 6.56), "0.39 mm de diferencia: es la medida en braqui_00.jpeg"
        assert not vb.fallos_de_la_meseta_comparable("p", 6.56, 5.60), "el signo no importa (0.96 mm)"
        assert vb.fallos_de_la_meseta_comparable("p", 6.17, 8.04), "1.87 mm: la referencia midio OTRA mancha (el umbral T = 16 de braqui)"
        assert vb.fallos_de_la_meseta_comparable("p", 5.91, 3.85), "2.06 mm: T = 8 en EPSON009"
        assert vb.fallos_de_la_meseta_comparable("p", None, 6.56), "el motor no dio ancho"
        assert vb.fallos_de_la_meseta_comparable("p", 6.17, None), "la referencia no dio ancho"

    def test_el_criterio_con_otras_mesetas_cae_si_una_meseta_comparable_difiere_mas_de_0_12_mm_y_no_juzga_las_incomparables(self):
        braqui_00 = {4: {"desfase_mm": -0.290, "ancho_mm": 6.01}, 8: {"desfase_mm": -0.375, "ancho_mm": 6.56}, 16: {"desfase_mm": -0.402, "ancho_mm": 8.04}}
        assert not vb.fallos_con_otras_mesetas("p", -0.362, 6.17, braqui_00), "los numeros medidos en braqui_00.jpeg: T = 4 (0.072 mm) y T = 8 (0.013 mm) comparables, T = 16 no"
        assert set(vb.umbrales_con_meseta_comparable(6.17, braqui_00)) == {4, 8}
        cerca = {**braqui_00, 4: {"desfase_mm": -0.250, "ancho_mm": 6.01}}
        assert not vb.fallos_con_otras_mesetas("p", -0.362, 6.17, cerca), "0.112 mm con una meseta comparable: bajo el limite de 0.12"
        lejos = {**braqui_00, 4: {"desfase_mm": -0.230, "ancho_mm": 6.01}}
        assert vb.fallos_con_otras_mesetas("p", -0.362, 6.17, lejos), "0.132 mm con una meseta comparable pasa el limite de 0.12"
        incomparable = {**braqui_00, 16: {"desfase_mm": 0.900, "ancho_mm": 8.04}}
        assert not vb.fallos_con_otras_mesetas("p", -0.362, 6.17, incomparable), "una meseta de 8.0 mm no es comparable con una de 6.2: no se juzga"
        assert vb.fallos_con_otras_mesetas("p", -0.362, 6.17, {16: braqui_00[16]}), "sin ninguna meseta comparable no hay con que comparar"
        assert vb.fallos_con_otras_mesetas("p", -0.362, 6.17, {}), "sin referencia alguna"
        assert not vb.fallos_con_otras_mesetas("p", -0.362, 6.17, {**braqui_00, 16: None}), "un umbral sin mancha se ignora"
        assert vb.fallos_con_otras_mesetas("p", None, 6.17, braqui_00), "el motor no mide el gris"
        assert vb.fallos_con_otras_mesetas("p", -0.362, None, braqui_00), "el motor no dio el ancho de su meseta"
