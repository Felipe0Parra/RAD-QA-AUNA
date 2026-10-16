"""B.2 (PLAN_ANALISIS_PELICULAS_08-10.md): el motor de la POSICION INICIAL de braquiterapia se compara con una VERDAD CONOCIDA, no consigo mismo ni con el cuaderno del fisico.

CAUSA. El motor acierta (error <= 0.03 mm en el gris contra un generador independiente) y el cuaderno del fisico, aun actualizado, se sesga en el gris (+0.625 mm), depende de los clics y falla en
la pagina; pero nada en la suite fijaba la exactitud del motor contra un generador que no fuera el suyo (la pestana sintetica de PI.5 usa `placa_sintetica` del motor): una «mejora» futura (la fila
unica, la fila entera sin ventana, la banda en los clics, el centro `primero + cuenta/2`) podia deshacerla sin que nada lo viera.

QUE FIJA ESTE ARCHIVO (la rejilla): los DOS generadores de PF.0 (`tests/_placa_braqui_sintetica.py`; el independiente y el fisico calibrado contra la mancha real; ninguno importa el motor), desfases
de -4 a +4 mm cada 0.25 mm (33 posiciones), la linea vertical e inclinada 1.5 grados, en PNG y en JPEG (8 combinaciones, 264 placas con ruido, la semilla es la posicion):
  * el error del motor es <= 0.05 mm en el gris y <= 0.10 mm en cada capa (R, G y B: cualquiera puede ser la reportada) -- con UN limite conocido, dicho y medido (ver `_verdad_braqui`): el modelo
    fisico con la linea sobre el borde de la meseta de la capa (|d| de 2.5 a 3.5 mm) llega a 0.147 mm en la AZUL (la de la meseta mas angosta; el plan pide 0.10) y solo en esa capa: el gris, la
    roja y la verde conservan el techo del plan tambien en la banda (ronda 1 de la revision: con otra relajacion una regresion de +0.10 mm en la roja o la verde pasaba sin que nada la viera);
  * la pendiente medido/verdadero es 1.00 +- 0.01;
  * mas alla de media meseta (|d| >= 3.25 mm) el motor da «No cumple» o «no medible» con su motivo, nunca «Cumple»;
  * la tasa de falsos «Cumple» y de falsos «No cumple» de cada capa es cero entre 0.75 y 1.25 mm (la tolerancia es de 1 mm);
  * el sentido FISICO (antes / despues de la marca) sigue a la banda de transito, y sin banda el motor no inventa uno.
Los criterios viven en `tests/_verdad_braqui.py` (una sola definicion: los guiones del anexo se los aplican tambien a copias mutadas del motor y a las replicas del cuaderno), y la clase
`TestLosCriteriosDiscriminan` prueba que cada uno CAE con un caso malo (un criterio que nunca cae no prueba nada).

Los casos dificiles (mancha corrida, meseta plana en JPEG, franja de transito, elipse girada, mancha chica, pagina entera) estan en `test_b2_braqui_casos_dificiles.py` y las placas reales
contra la referencia independiente en `test_b2_braqui_placas_reales.py`. Esta prueba no toca produccion (riesgo NULO).
"""
import dataclasses

import pytest

import _placa_braqui_sintetica as pb
import _verdad_braqui as vb


@pytest.fixture(scope="module", autouse=True)
def _suelta_las_rejillas_al_terminar_el_modulo():
    """B.4 (deuda heredada de B.3, R1-LD-02): las rejillas que `vb.rejilla` guarda por proceso se sueltan al terminar el modulo; las heredarian los archivos siguientes de su reparto."""
    yield
    vb.liberar_las_rejillas()


COMBINACIONES = [(m, i, f) for m in ("independiente", "fisico") for i in (False, True) for f in vb.FORMATOS]
IDENTIFICADORES = [f"{m}-{'inclinada' if i else 'vertical'}-{f}" for m, i, f in COMBINACIONES]


@pytest.fixture(scope="module", params=COMBINACIONES, ids=IDENTIFICADORES)
def casos(request):
    """Los 33 casos medidos de una combinacion (generador, linea vertical o inclinada, formato)."""
    return vb.rejilla(*request.param)


COMBINACIONES_DEL_FISICO = [c for c in COMBINACIONES if c[0] == "fisico"]
IDENTIFICADORES_DEL_FISICO = [i for c, i in zip(COMBINACIONES, IDENTIFICADORES) if c[0] == "fisico"]


@pytest.fixture(scope="module", params=COMBINACIONES_DEL_FISICO, ids=IDENTIFICADORES_DEL_FISICO)
def casos_del_fisico(request):
    """Los 33 casos medidos de cada combinacion del modelo FISICO (los mismos que `casos`: `vb.rejilla` los guarda por proceso). Un control que solo vale para este modelo no se parametriza con un skip (T10)."""
    return vb.rejilla(*request.param)


def _con_error(caso, capa, error):
    """El mismo caso con UNA capa que mide `error` mm mas que la verdad (el veredicto sigue al numero): la regresion que una prueba debe ver."""
    medida = caso.medicion.medidas[capa]
    mm = caso.esperado_mm + error
    medidas = dict(caso.medicion.medidas)
    medidas[capa] = dataclasses.replace(medida, estado="ok", mm=mm, veredicto="Cumple" if abs(mm) <= vb.TOLERANCIA_MM else "No cumple")
    return dataclasses.replace(caso, medicion=dataclasses.replace(caso.medicion, medidas=medidas))


def _con_la_regresion_en_la_banda(casos, capa, error):
    """Los `casos` con `error` mm en `capa` en TODA posicion de la banda del limite conocido (sin tocar nada fuera de ella)."""
    return [_con_error(c, capa, error if c.verdad.desfase_mm > 0 else -error) if vb.en_la_banda_del_limite_conocido(c.modelo, c.verdad.desfase_mm) else c for c in casos]


class TestLaRejillaDeDesfases:
    def test_la_rejilla_cubre_de_menos_4_a_mas_4_mm_cada_cuarto_de_mm(self, casos):
        assert len(casos) == 33
        assert [c.desfase for c in casos] == [-4.0 + 0.25 * k for k in range(33)]
        for c in casos:
            assert c.verdad.desfase_mm == pytest.approx(c.desfase), "sin rotar la pagina la verdad es el desfase pedido"
            assert set(c.medicion.medidas) == {"gris", "R", "G", "B"}

    def test_exactitud_gris_0_05_mm_y_cada_capa_0_10_mm_salvo_la_azul_en_la_banda_del_limite_conocido(self, casos):
        """El criterio del plan en toda posicion y en toda capa; lo unico que se juzga aparte es la capa AZUL del modelo fisico en su banda del limite conocido (la prueba siguiente)."""
        fallos = vb.fallos_de_exactitud(casos)
        assert not fallos, f"{len(fallos)} fallos:\n" + "\n".join(fallos[:12])
        juzgadas = [(c, capa) for c in casos for capa in vb.CAPAS if not vb.en_la_banda_del_limite_conocido(c.modelo, c.verdad.desfase_mm, capa)]
        assert len(juzgadas) == (33 * 4 if casos[0].modelo == "independiente" else 33 * 4 - 8), \
            "el independiente se juzga en las 33 posiciones y las 4 capas; el fisico, salvo la azul en las 8 posiciones de la banda (de 2.75 a 3.5 mm de cada lado): el gris, la roja y la verde conservan el techo del plan"
        if casos[0].modelo == "fisico":
            en_la_banda = [c for c in casos if vb.en_la_banda_del_limite_conocido(c.modelo, c.verdad.desfase_mm)]
            assert len(en_la_banda) == 8 and all(vb.techo_de("fisico", capa, c.verdad.desfase_mm) == vb.TECHO_DEL_ERROR_MM[capa] for c in en_la_banda for capa in ("gris", "R", "G"))

    def test_en_la_banda_del_limite_conocido_el_error_de_la_azul_queda_bajo_el_techo_medido(self, casos):
        fallos = vb.fallos_del_limite_conocido(casos)
        assert not fallos, "\n".join(fallos[:12])
        if casos[0].modelo == "independiente":
            assert vb.BANDA_DEL_BORDE.get("independiente") is None, "el generador independiente cumple el criterio del plan en toda posicion: no tiene limite conocido"

    def test_pendiente_medido_sobre_verdadero_1_00_mas_menos_0_01(self, casos):
        fallos = vb.fallos_de_la_pendiente(casos)
        assert not fallos, "\n".join(fallos)

    def test_mas_alla_de_media_meseta_el_motor_da_no_cumple_o_no_medible_con_motivo_nunca_cumple(self, casos):
        fallos = vb.fallos_mas_alla_de_media_meseta(casos)
        assert not fallos, f"{len(fallos)} fallos:\n" + "\n".join(fallos[:12])
        mas_alla = [c for c in casos if abs(c.verdad.desfase_mm) >= vb.MEDIA_MESETA_MM]
        assert len(mas_alla) == 8, "de -4 a -3.25 y de 3.25 a 4 hay 4 posiciones por lado"

    def test_falsos_cumple_y_falsos_no_cumple_son_cero_entre_0_75_y_1_25_mm(self, casos):
        fallos = vb.fallos_del_veredicto(casos)
        assert not fallos, "\n".join(fallos)
        for capa in vb.CAPAS:
            falsos_cumple, n_fuera, falsos_no_cumple, n_dentro = vb.tasas_de_falsos(casos, capa)
            assert (n_fuera, n_dentro) == (2, 2), "dos posiciones claras por lado: |d| = 1.25 (fuera) y |d| = 0.75 (dentro)"
            assert falsos_cumple == 0 and falsos_no_cumple == 0

    def test_el_veredicto_sigue_al_numero_que_el_motor_da(self, casos):
        fallos = vb.fallos_de_coherencia_del_veredicto(casos)
        assert not fallos, f"{len(fallos)} fallos:\n" + "\n".join(fallos[:12])

    def test_sentido_fisico_sigue_a_la_banda_de_transito_y_sin_banda_no_se_inventa(self, casos):
        fallos = vb.fallos_del_sentido_fisico(casos) if casos[0].modelo == "fisico" else vb.fallos_de_no_decir_un_sentido_sin_banda(casos)
        assert not fallos, "\n".join(fallos[:8])
        if casos[0].modelo == "fisico":
            # el generador fisico trae la banda por el cable: el motor la ve a la derecha en toda la zona plena y el sentido sale de ella
            plena = [c for c in casos if abs(c.verdad.desfase_mm) <= vb.ZONA_PLENA_MM]
            assert {c.medicion.lado_transito for c in plena} == {"derecha"}


class TestElLimiteConocidoDelModeloFisico:
    def test_la_banda_del_limite_conocido_es_el_borde_de_la_meseta_de_la_capa_azul(self):
        """Ancla del limite a la fisica: la meseta saturada de cada capa del modelo fisico (medida sobre la imagen sin ruido ni linea, por la funcion independiente de PF.0) tiene su semiancho dentro de la
        banda del borde; la capa AZUL, la de la meseta mas angosta, es la UNICA que declara un limite (las demas conservan el techo del plan: ronda 1 de la revision) y la zona plena queda por debajo del
        semiancho de la capa mas angosta menos el medio ancho de la linea."""
        semianchos = vb.semianchos_de_la_meseta_fisica()
        desde, hasta, techos = vb.BANDA_DEL_BORDE["fisico"]
        assert set(semianchos) == {"gris", "B", "G", "R"}
        for capa, semiancho in semianchos.items():
            assert desde < semiancho <= hasta, f"el semiancho de la meseta {capa} ({semiancho:.2f} mm) no cae en la banda ({desde}, {hasta}]"
        assert set(techos) == {"B"}, "solo la capa azul declara un limite conocido: el gris, la roja y la verde miden bajo el techo del plan en la banda"
        assert min(semianchos.values()) == pytest.approx(semianchos["B"]), "la capa azul es la de la meseta mas angosta"
        assert vb.ZONA_PLENA_MM + 0.5 <= min(semianchos.values()), "la zona plena deja medio milimetro entre la linea y el borde de la meseta mas angosta"

    def test_el_techo_del_plan_vale_en_todas_partes_menos_en_la_azul_de_la_banda_del_modelo_fisico(self):
        for capa, techo in vb.TECHO_DEL_ERROR_MM.items():
            for d in (0.0, 1.0, 2.5, 3.75, 4.0, -2.5, -3.75):
                assert vb.techo_de("fisico", capa, d) == techo
            for d in (-4.0, -3.0, 0.0, 3.0, 3.5, 4.0):
                assert vb.techo_de("independiente", capa, d) == techo, "el generador independiente no necesita limite conocido"
            for d in (2.75, 3.0, 3.25, 3.5, -3.5):
                if capa == "B":
                    assert vb.techo_de("fisico", capa, d) > techo, "la banda del borde relaja el techo de la azul del modelo fisico"
                else:
                    assert vb.techo_de("fisico", capa, d) == techo, f"{capa}: el techo del plan vale tambien en la banda (el limite conocido es solo de la azul)"
        assert vb.techo_de("fisico", "B", -3.0) == 0.20 and vb.techo_de("fisico", "gris", 3.0) == 0.05 and vb.techo_de("fisico", "R", 3.0) == vb.techo_de("fisico", "G", -3.0) == 0.10
        assert vb.capas_con_limite_conocido("fisico") == ("B",) and vb.capas_con_limite_conocido("independiente") == ()

    def test_sin_la_banda_el_criterio_literal_del_plan_solo_cae_en_la_comparacion_que_el_limite_conocido_declara(self, monkeypatch):
        """El limite conocido esta RESPALDADO por lo medido y no es mas ancho que ello (hallazgo DL-01: una relajacion sin una comparacion que la respalde deja una zona ciega). Sin la banda, el criterio literal del plan
        cae en EXACTAMENTE una de las 528 comparaciones del modelo fisico (4 combinaciones x 33 posiciones x 4 capas): la azul, con JPEG, la linea inclinada y d = +3.25 mm (0.147 mm contra 0.10). Y las capas que
        declaran el limite son exactamente las que exceden. Si una mejora del motor la lleva bajo 0.10 mm, el limite sobra y hay que quitarlo; si cae otra comparacion, hay un exceso nuevo que nadie declara."""
        casos = [c for combinacion in COMBINACIONES_DEL_FISICO for c in vb.rejilla(*combinacion)]
        assert len(casos) * len(vb.CAPAS) == 528
        declaradas = set(vb.capas_con_limite_conocido("fisico"))
        monkeypatch.setattr(vb, "BANDA_DEL_BORDE", {})
        literal = vb.fallos_de_exactitud(casos)
        assert len(literal) == 1 and literal[0].startswith("fisico/inclinada/jpeg/d=+3.25 B: error +0.1"), \
            f"la unica desviacion del criterio literal del plan: la azul, JPEG, inclinada, d = +3.25 mm (0.147 mm); {len(literal)} fallos: {literal[:4]}"
        assert {f.split()[1].rstrip(":") for f in literal} == declaradas == {"B"}, "las capas que declaran el limite conocido son exactamente las que exceden el techo del plan"

    def test_una_regresion_en_la_banda_se_ve_en_el_gris_la_roja_y_la_verde_con_los_techos_del_plan(self, casos_del_fisico):
        """Hallazgo DL-01 de la revision (ronda 1): con el techo relajado (gris 0.08, capa 0.20) en TODAS las capas de la banda, una regresion de +0.10 mm en la roja y la verde y de +0.03 mm en el gris pasaba
        los seis criterios de la rejilla. Aqui se fabrica, sobre los casos MEDIDOS del modelo fisico, un error de un centesimo de mm sobre el techo del plan en UNA capa y en las 8 posiciones de la banda: el
        criterio la tiene que nombrar (y solo a esa capa)."""
        assert not vb.fallos_de_exactitud(casos_del_fisico) and not vb.fallos_del_limite_conocido(casos_del_fisico), "punto de partida: los casos medidos pasan"
        for capa in ("gris", "R", "G"):
            fabricados = _con_la_regresion_en_la_banda(casos_del_fisico, capa, vb.TECHO_DEL_ERROR_MM[capa] + 0.01)
            fallos = vb.fallos_de_exactitud(fabricados)
            assert len(fallos) == 8 and all(f" {capa}: error " in f for f in fallos), (capa, fallos[:3])
            assert not vb.fallos_del_limite_conocido(fabricados), "el limite conocido es de la azul: no juzga el gris, la roja ni la verde"

    def test_en_la_azul_de_la_banda_el_techo_es_el_medido_con_margen_y_no_el_del_plan(self, casos_del_fisico):
        """La capa azul con la linea sobre el borde de su meseta mide hasta 0.147 mm (el plan pide 0.10): 0.11 mm pasa (es el limite conocido) y 0.21 mm no (el techo medido con margen es 0.20)."""
        entre = _con_la_regresion_en_la_banda(casos_del_fisico, "B", vb.TECHO_DEL_ERROR_MM["B"] + 0.01)
        assert not vb.fallos_de_exactitud(entre) and not vb.fallos_del_limite_conocido(entre)
        sobre = _con_la_regresion_en_la_banda(casos_del_fisico, "B", 0.20 + 0.01)
        fallos = vb.fallos_del_limite_conocido(sobre)
        assert len(fallos) == 8 and all(" B: error " in f for f in fallos), fallos[:3]
        assert not vb.fallos_de_exactitud(sobre), "la azul de la banda la juzga el limite conocido y no la exactitud del plan"


# --------------------------------------------------------------------------------------------------------------------------- los criterios discriminan
def _caso(d, medidas, modelo="independiente", sentido=None, lado=None):
    return vb.caso_a_mano(d, medidas, modelo, sentido, lado)


class TestLosCriteriosDiscriminan:
    """Cada criterio de `_verdad_braqui` cae con un caso malo y pasa con uno bueno: un criterio que nunca cae no detecta nada (Trampa 8)."""

    def test_exactitud_cae_con_un_error_de_0_06_en_el_gris_o_de_0_11_en_una_capa_o_una_capa_no_medida_en_la_zona_plena(self):
        assert not vb.fallos_de_exactitud([_caso(1.0, {"gris": (1.045, "Cumple")})]), "0.045 mm en el gris esta bajo el techo de 0.05"
        assert not vb.fallos_de_exactitud([_caso(1.0, {"B": (1.095, "No cumple")})])
        assert vb.fallos_de_exactitud([_caso(1.0, {"gris": (1.06, "No cumple")})])
        assert vb.fallos_de_exactitud([_caso(1.0, {"R": (0.89, "Cumple")})])
        assert vb.fallos_de_exactitud([_caso(0.5, {"G": (None, "no medible: la linea tapa el borde de la meseta")})]), "dentro de la zona plena toda capa se mide"
        assert not vb.fallos_de_exactitud([_caso(3.9, {"G": (None, "no medible: la linea tapa el borde de la meseta")})]), "fuera de la zona plena puede no medirse"

    def test_el_limite_conocido_cae_con_un_error_de_la_azul_sobre_el_techo_medido_y_la_exactitud_juzga_las_demas_capas_en_la_banda(self):
        dentro = [_caso(3.0, {"B": (3.15, "No cumple")}, modelo="fisico")]
        assert not vb.fallos_del_limite_conocido(dentro) and not vb.fallos_de_exactitud(dentro), "0.15 mm en la azul con la linea sobre el borde: bajo el techo medido (0.20) y fuera del criterio estricto"
        assert vb.fallos_del_limite_conocido([_caso(3.0, {"B": (3.25, "No cumple")}, modelo="fisico")]), "0.25 mm pasa el techo medido de 0.20"
        assert vb.fallos_del_limite_conocido([_caso(3.0, {"B": (None, "no medible")}, modelo="fisico")]), "la azul sin medir en la banda tiene que decir por que"
        assert not vb.fallos_del_limite_conocido([_caso(3.0, {"B": (None, "no medible: la linea tapa el borde de la meseta")}, modelo="fisico")])
        # las demas capas, EN la banda, con el techo del plan (hallazgo DL-01 de la ronda 1)
        assert not vb.fallos_de_exactitud([_caso(3.0, {"gris": (3.045, "No cumple")}, modelo="fisico")]), "0.045 mm en el gris con la linea sobre el borde: bajo el techo del plan"
        assert vb.fallos_de_exactitud([_caso(3.0, {"gris": (3.06, "No cumple")}, modelo="fisico")]), "0.06 mm en el gris: sobre el techo del plan (0.05) aunque el limite de la azul sea 0.20"
        assert vb.fallos_de_exactitud([_caso(3.0, {"R": (3.15, "No cumple")}, modelo="fisico")]), "0.15 mm en la roja"
        assert vb.fallos_de_exactitud([_caso(-3.0, {"G": (-3.11, "No cumple")}, modelo="fisico")]), "0.11 mm en la verde"
        assert not vb.fallos_de_exactitud([_caso(3.0, {"G": (3.095, "No cumple")}, modelo="fisico")]), "0.095 mm en la verde: bajo el techo del plan"
        assert vb.fallos_de_exactitud([_caso(3.0, {"G": (None, "no medible")}, modelo="fisico")]), "una capa que no es la azul y no se mide, sin decir por que, cae tambien en la banda"
        assert vb.fallos_del_limite_conocido([_caso(1.0, {}, modelo="fisico")]), "sin ningun caso en la banda no hay nada que probar"
        assert not vb.fallos_del_limite_conocido([_caso(1.0, {}, modelo="independiente")]), "el independiente no tiene banda: no hay nada que juzgar"
        assert vb.fallos_de_exactitud([_caso(3.0, {"B": (3.15, "No cumple")}, modelo="independiente")]), "el independiente se juzga con el techo del plan en toda posicion"
        assert vb.fallos_de_exactitud([_caso(2.0, {"B": (2.15, "No cumple")}, modelo="fisico")]), "fuera de la banda el fisico tambien"
        assert vb.fallos_de_exactitud([_caso(3.9, {"G": (None, "no medible")}, modelo="independiente")]), "sin motivo, una capa que no se mide cae tambien fuera de la zona plena"

    def test_la_coherencia_del_veredicto_cae_con_un_veredicto_que_no_sigue_al_numero(self):
        assert not vb.fallos_de_coherencia_del_veredicto([_caso(0.5, {}), _caso(1.5, {}), _caso(2.0, {"G": (None, "no medible: x")})] + [_caso(1.0, {})])
        assert vb.fallos_de_coherencia_del_veredicto([_caso(1.5, {"G": (1.5, "Cumple")})]), "1.5 mm es «No cumple»"
        assert vb.fallos_de_coherencia_del_veredicto([_caso(0.5, {"R": (0.5, "No cumple")})]), "0.5 mm es «Cumple»"
        sin_medir = _caso(0.5, {})
        sin_medir.medicion.medidas["G"] = vb.Medida("no medible: x", None, "Cumple")
        assert vb.fallos_de_coherencia_del_veredicto([sin_medir]), "lo que no se mide no puede tener veredicto"
        assert vb.fallos_de_coherencia_del_veredicto([_caso(0.5, {c: (None, "no medible: x") for c in vb.CAPAS})]), "sin ninguna capa medida no hay nada que juzgar"

    def test_pendiente_cae_con_una_pendiente_de_0_98_o_de_1_02_o_con_pocas_posiciones(self):
        buenos = [_caso(-3.0 + 0.25 * k, {}) for k in range(25)]
        assert not vb.fallos_de_la_pendiente(buenos)
        escala = lambda f: [_caso(-3.0 + 0.25 * k, {c: ((-3.0 + 0.25 * k) * f, "No cumple") for c in vb.CAPAS}) for k in range(25)]
        assert len(vb.fallos_de_la_pendiente(escala(0.98))) == 4 and len(vb.fallos_de_la_pendiente(escala(1.02))) == 4
        assert not vb.fallos_de_la_pendiente(escala(1.009)) and not vb.fallos_de_la_pendiente(escala(0.991))
        assert vb.fallos_de_la_pendiente(buenos[:10])

    def test_mas_alla_de_media_meseta_cae_con_un_cumple_o_con_un_no_medible_sin_motivo(self):
        bien = [_caso(3.5, {}), _caso(-4.0, {"B": (None, "no medible: la mancha se sale de la zona marcada")})]
        assert not vb.fallos_mas_alla_de_media_meseta(bien)
        assert vb.fallos_mas_alla_de_media_meseta([_caso(3.5, {"G": (0.9, "Cumple")})]), "un «Cumple» a 3.5 mm de la marca"
        assert vb.fallos_mas_alla_de_media_meseta([_caso(3.5, {"R": (None, "no medible")})]), "no medible sin decir por que"
        assert vb.fallos_mas_alla_de_media_meseta([_caso(3.5, {"R": (None, "")})])
        assert vb.fallos_mas_alla_de_media_meseta([_caso(0.5, {})]), "sin ningun caso mas alla de media meseta no hay nada que probar"

    def test_el_veredicto_cae_con_un_falso_cumple_o_un_falso_no_cumple_entre_0_75_y_1_25_mm(self):
        claros = lambda **kw: [_caso(d, kw) for d in (-1.25, -0.75, 0.75, 1.25)]
        assert not vb.fallos_del_veredicto(claros())
        assert vb.fallos_del_veredicto(claros(R=(1.25, "Cumple")))               # falso «Cumple» con |d| = 1.25 (en dos casos)
        assert vb.fallos_del_veredicto(claros(gris=(0.75, "No cumple")))         # falso «No cumple» con |d| = 0.75
        assert vb.fallos_del_veredicto([_caso(0.0, {})]), "sin casos claros no hay tasa"
        assert not vb.fallos_del_veredicto(claros() + [_caso(1.0, {"G": (1.02, "No cumple")})]), "en la zona de duda (|d| = 1.0) el veredicto puede ir a cualquier lado"

    def test_el_sentido_fisico_cae_con_el_sentido_contrario_o_sin_ningun_caso(self):
        bien = [_caso(1.0, {}, modelo="fisico", sentido="despues de la marca", lado="derecha"), _caso(-1.0, {}, modelo="fisico", sentido="antes de la marca", lado="derecha")]
        assert not vb.fallos_del_sentido_fisico(bien)
        mal = _caso(1.0, {}, modelo="fisico", sentido="despues de la marca", lado="derecha")
        mal.medicion.medidas["gris"] = vb.Medida("ok", 1.0, "Cumple", "antes de la marca")
        assert vb.fallos_del_sentido_fisico([mal])
        assert vb.fallos_del_sentido_fisico([_caso(0.1, {}, modelo="fisico", sentido="despues de la marca")]), "a menos de 0.25 mm de la marca no se compara"
        inventado = _caso(1.0, {}, sentido=None, lado="derecha")
        assert vb.fallos_de_no_decir_un_sentido_sin_banda([inventado]), "sin banda de transito el motor no puede decir un lado"

    def test_las_posiciones_de_la_rejilla_son_las_que_dice_el_plan(self):
        assert vb.DESFASES_DE_LA_REJILLA[0] == -4.0 and vb.DESFASES_DE_LA_REJILLA[-1] == 4.0 and len(vb.DESFASES_DE_LA_REJILLA) == 33
        assert vb.TECHO_DEL_ERROR_MM == {"gris": 0.05, "R": 0.10, "G": 0.10, "B": 0.10}
        assert vb.BANDA_DEL_BORDE == {"fisico": (2.5, 3.5, {"B": 0.20})}, "el unico limite conocido: la capa azul del modelo fisico, de 2.5 a 3.5 mm, con el techo medido 0.147 y margen"
        assert (vb.PENDIENTE_MINIMA, vb.PENDIENTE_MAXIMA, vb.TOLERANCIA_MM, vb.INCLINACION_DE_LA_LINEA_DEG) == (0.99, 1.01, 1.0, 1.5)
        assert pb.MM_POR_PX == pytest.approx(25.4 / 600.0)
