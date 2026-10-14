"""B.2 (PLAN_ANALISIS_PELICULAS_08-10.md): los CASOS DIFICILES de la posicion inicial de braquiterapia, medidos con las seis variantes de PF.0 (`VARIANTES_DIFICILES` de `_placa_braqui_sintetica.py`)
en los dos generadores (el independiente y el fisico calibrado), con ruido y en JPEG. Son exactamente los casos donde una «simplificacion» del motor fallaria, y donde el cuaderno del fisico (V2 de las
17:03 y V3 de las 08:53) falla: la fila unica del cuaderno, su fila entera sin ventana y su banda alrededor del punto medio de los clics. Cada criterio es una funcion de `tests/_verdad_braqui.py`:

  * MANCHA CORRIDA: la mancha a 60 px (2.5 mm) del punto medio de los clics se mide a <= 0.10 mm en el gris y en cada capa;
  * MESETA PLANA EN JPEG (como braqui_00: plana en 1, casi sin ruido): <= 0.10 mm;
  * FRANJA DE TRANSITO DE UN SOLO LADO (al 90, 95 y 97 % del tope, a los dos lados): <= 0.10 mm o «no medible» con su motivo, nunca un numero peor (la azul puede no medirse). En el modelo fisico la
    franja x 5 corre el punto medio unos -0.10 mm POR FISICA, no por el motor: se compara contra el punto medio aparente que mide el generador sobre la imagen sin ruido (sin el motor);
  * ELIPSE 6 x 9 mm GIRADA 10, 15 y 20 grados: sesgo <= 0.05 mm, centrada en los clics y corrida 60 px (la banda alrededor de los clics se sesga 0.3-0.45 mm aqui); su error maximo (0.31 a 0.49 mm
    medido) queda fijado como LIMITE CONOCIDO: el motor descarta de forma asimetrica las filas con un borde tapado por la linea;
  * MANCHA CHICA de 4.5 mm: dispersion <= 0.03 mm en el gris;
  * PAGINA ENTERA: la misma placa recortada y en pagina da lo mismo +-0.02 mm; una pagina con un bloque negro fuera de la ventana de analisis se mide igual (la fila entera sin ventana pierde la
    mancha); y la pagina rotada 90, 180 y 270 grados sigue a la VERDAD DE LA IMAGEN DEVUELTA (PF.0), con el mismo sentido fisico.

Hallazgo de la medicion (14-10), que el plan preveia («se acepta»): con la franja de transito el motor no mide la capa azul en 16 de 30 placas del generador independiente; el gris, la roja y la verde se
miden siempre. Y un hallazgo menor: con la meseta plana en JPEG la verde no se mide a +1.5 mm (la linea cae a 0.3-0.5 mm del borde de una meseta de 3.5 mm): dice por que, no da un numero peor.
Esta prueba no toca produccion (riesgo NULO).
"""
import pytest

import _placa_braqui_sintetica as pb
import _verdad_braqui as vb

MODELOS = ("independiente", "fisico")


def _fixture(receta):
    """Una fixture de modulo por (receta, generador): (modelo, encargos, casos medidos)."""
    @pytest.fixture(scope="module", params=MODELOS)
    def fx(request):
        encargos = receta(request.param)
        return request.param, encargos, vb.hacer_casos(encargos)
    return fx


mancha_corrida = _fixture(lambda m: vb.encargos_de_una_variante(m, "mancha_corrida"))
meseta_plana = _fixture(lambda m: vb.encargos_de_una_variante(m, "meseta_plana_jpeg"))
transito = _fixture(vb.encargos_del_transito)
elipse = _fixture(vb.encargos_de_la_elipse)
mancha_chica = _fixture(lambda m: vb.encargos_de_una_variante(m, "mancha_chica"))
pagina_y_recorte = _fixture(vb.encargos_de_pagina_y_recorte)
bloque_negro = _fixture(vb.encargos_con_un_objeto_oscuro)
pagina_rotada = _fixture(vb.encargos_de_la_pagina_rotada)


def _sin_fallos(fallos):
    assert not fallos, f"{len(fallos)} fallos:\n" + "\n".join(fallos[:12])


class TestManchaCorrida:
    def test_la_mancha_esta_a_60_px_del_punto_medio_de_los_clics(self, mancha_corrida):
        """La premisa del caso: la variante corre la mancha ~60 px (2.5 mm) a lo largo de la linea respecto del punto medio de los clics."""
        modelo, encargos, casos = mancha_corrida
        for e in encargos:
            cy_clics = sum(c[1] for c in e.placa.clics) / 2.0
            cy_mancha = e.placa.verdad.centro_mancha_px[1]
            assert 58.0 <= abs(cy_mancha - cy_clics) <= 61.0, f"{e.etiqueta}: la mancha esta a {abs(cy_mancha - cy_clics):.1f} px del punto medio de los clics"

    def test_la_mancha_a_60_px_del_punto_medio_de_los_clics_se_mide_a_0_10_mm(self, mancha_corrida):
        modelo, encargos, casos = mancha_corrida
        assert len(casos) == len(vb.DESFASES_DIFICILES)
        _sin_fallos(vb.fallos_de_error_maximo(casos, minimo_medidas=len(casos)))


class TestMesetaPlanaEnJpeg:
    def test_la_placa_es_un_jpeg_con_la_meseta_plana(self, meseta_plana):
        modelo, encargos, casos = meseta_plana
        for e in encargos:
            assert e.placa.formato == "jpeg" and e.placa.datos[:2] == b"\xff\xd8"
            if modelo == "independiente":
                assert e.placa.verdad.parametros["nivel_meseta"] == 1.0 and e.placa.verdad.parametros["ruido"] == 0.15
            else:
                assert e.placa.verdad.parametros["escenario"] == "plana1" and e.placa.verdad.parametros["piso_escaner"] == 1.0

    def test_la_meseta_plana_en_jpeg_se_mide_a_0_10_mm_o_dice_por_que_no(self, meseta_plana):
        modelo, encargos, casos = meseta_plana
        _sin_fallos(vb.fallos_de_error_maximo(casos, admite_no_medible=True, minimo_medidas=7))
        assert all(c.medicion.medidas["gris"].mm is not None for c in casos), "el gris se mide siempre"


class TestFranjaDeTransitoDeUnSoloLado:
    def test_la_franja_esta_de_un_solo_lado_y_a_los_niveles_pedidos(self, transito):
        modelo, encargos, casos = transito
        if modelo == "independiente":
            combinaciones = {(e.placa.verdad.parametros["transito"], e.placa.verdad.lado_transito) for e in encargos}
            assert combinaciones == {(n, l) for n in (0.90, 0.95, 0.97) for l in (+1, -1)}, "tres niveles del tope, a la derecha y a la izquierda"
        else:
            assert {e.placa.verdad.parametros["escenario"] for e in encargos} == {"transito_x5"}
            assert {e.placa.verdad.lado_transito for e in encargos} == {+1}

    def test_gris_roja_y_verde_se_miden_a_0_10_mm_y_la_azul_se_mide_o_dice_por_que_no(self, transito):
        modelo, encargos, casos = transito
        _sin_fallos(vb.fallos_del_transito(casos))

    def test_el_corrimiento_fisico_que_se_descuenta_es_pequeno_y_no_sale_del_motor(self, transito):
        modelo, encargos, casos = transito
        if modelo == "independiente":
            assert all(c.objetivo is None for c in casos), "el generador independiente no corre el punto medio: se juzga contra la verdad"
            return
        _sin_fallos(vb.fallos_del_corrimiento_fisico(casos))
        corrimientos = [c.objetivo - c.verdad.desfase_mm for c in casos]
        assert -0.12 < min(corrimientos) and max(corrimientos) < -0.05, f"la franja x 5 corre el punto medio ~-0.09 mm por fisica: {corrimientos}"


class TestElipseGirada:
    def test_la_elipse_es_de_6_por_9_mm_y_esta_girada_y_corrida_como_se_pide(self, elipse):
        modelo, encargos, casos = elipse
        if modelo == "fisico":
            assert {e.placa.verdad.parametros["escenario"] for e in encargos} == {"cateter_oblicuo_15"}
            return
        grupos = {e.grupo for e in encargos}
        assert grupos == {("independiente", g, dv) for g in vb.GIROS_DE_LA_ELIPSE_DEG for dv in (60.0,)} | {("independiente", 15.0, 0.0)}
        for e in encargos:
            p = e.placa.verdad.parametros
            assert (p["ancho_mm"], p["alto_mm"]) == (6.0, 9.0) and p["giro_elipse_deg"] == e.grupo[1] and p["dv_mancha_px"] == e.grupo[2]

    def test_el_sesgo_es_de_0_05_mm_y_el_error_maximo_queda_bajo_el_limite_conocido(self, elipse):
        modelo, encargos, casos = elipse
        por_grupo = vb.grupos_de(list(zip(encargos, casos)))
        _sin_fallos(vb.fallos_de_la_elipse(por_grupo))


class TestManchaChica:
    def test_la_mancha_es_de_4_5_mm(self, mancha_chica):
        modelo, encargos, casos = mancha_chica
        for e in encargos:
            p = e.placa.verdad.parametros
            if modelo == "independiente":
                assert (p["ancho_mm"], p["alto_mm"]) == (4.5, 4.5)
            else:
                assert p["escenario"] == "mancha_chica" and p["cuerda_mm"] == 4.5

    def test_la_dispersion_es_de_0_03_mm_en_el_gris_y_las_capas_que_no_se_miden_dicen_por_que(self, mancha_chica):
        modelo, encargos, casos = mancha_chica
        _sin_fallos(vb.fallos_de_la_mancha_chica(casos))


class TestPaginaEntera:
    def test_la_misma_placa_recortada_y_en_pagina_entera_mide_lo_mismo_a_0_02_mm(self, pagina_y_recorte):
        modelo, encargos, casos = pagina_y_recorte
        formas = {e.grupo[0]: e.placa.imagen.shape[:2] for e in encargos}
        assert formas["recorte"] == pb.FORMA and formas["pagina"] == pb.PAGINA_PX, "una es el recorte y la otra la hoja entera del escaner"
        _sin_fallos(vb.fallos_de_pagina_contra_recorte(list(zip(encargos, casos))))

    def test_una_pagina_con_un_bloque_negro_fuera_de_la_ventana_se_mide_igual(self, bloque_negro):
        """El bloque negro (60 a 120 mm de la linea, fuera de la ventana de +-20 mm) es lo mas ancho y oscuro de la fila: sin la ventana el motor lo toma por la mancha («la mancha se sale de la zona marcada»)."""
        modelo, encargos, casos = bloque_negro
        for e in encargos:
            img = e.placa.imagen
            x0, y0 = e.placa.verdad.pagina["origen"]
            x_linea = int(x0 + e.placa.verdad.x_linea)
            fila = img[y0 + pb.FORMA[0] // 2, :, :].sum(axis=1)
            negro = int((fila == 0).sum())
            assert negro > 1000, f"{e.etiqueta}: el bloque negro mide {negro} px de ancho en la fila"
            assert (fila[x_linea + int(60.0 / pb.MM_POR_PX) + 5:x_linea + int(110.0 / pb.MM_POR_PX)] == 0).all(), "el bloque negro empieza a 60 mm de la linea"
            mm = lambda v: int(v / pb.MM_POR_PX)
            assert (fila[x_linea + mm(25.0):x_linea + mm(59.0)] > 0).all() and (fila[max(0, x_linea - mm(120.0)):x_linea - mm(25.0)] > 0).all(), \
                "entre la zona de la mancha (a 25 mm de la linea) y el bloque no hay nada negro, ni a la izquierda de la linea"
        _sin_fallos(vb.fallos_de_exactitud(casos))

    def test_la_pagina_rotada_sigue_a_la_verdad_de_la_imagen_devuelta_con_el_mismo_sentido_fisico(self, pagina_rotada):
        modelo, encargos, casos = pagina_rotada
        assert {e.placa.verdad.pagina["rotar_k90"] for e in encargos} == {1, 2, 3}
        # el desfase de la verdad cambia de signo con 1 y 2 giros (PF.0): la prueba falla si el motor mide el de la escena sin rotar
        cambian = [c for c, e in zip(casos, encargos) if e.placa.verdad.pagina["rotar_k90"] in (1, 2) and c.desfase != 0.0]
        assert cambian and all(c.verdad.desfase_mm == pytest.approx(-c.desfase) for c in cambian)
        _sin_fallos(vb.fallos_de_la_pagina_rotada(casos))


# --------------------------------------------------------------------------------------------------------------------------- los criterios discriminan
def _caso(d, medidas=None, **kw):
    return vb.caso_a_mano(d, medidas, **kw)


class TestLosCriteriosDeLosCasosDificilesDiscriminan:
    """Cada criterio de los casos dificiles cae con un caso malo y pasa con uno bueno (Trampa 8: un criterio que nunca cae no detecta nada)."""

    def test_el_error_maximo_cae_con_0_11_mm_o_con_una_capa_sin_medir_sin_motivo_o_con_pocas_medidas(self):
        buenos = [_caso(d, {"R": (d + 0.09, "Cumple")}) for d in (-1.0, 0.0, 1.0)]
        assert not vb.fallos_de_error_maximo(buenos, minimo_medidas=3)
        assert vb.fallos_de_error_maximo([_caso(0.0, {"G": (0.11, "Cumple")})]), "0.11 mm pasa el techo de 0.10"
        assert vb.fallos_de_error_maximo([_caso(0.0, {"gris": (0.11, "Cumple")})]), "el gris tambien se juzga a 0.10 en los casos dificiles"
        con_motivo = [_caso(0.0, {"B": (None, "no medible: la linea tapa el borde de la meseta")}), _caso(1.0)]
        sin_motivo = [_caso(0.0, {"B": (None, "no medible")}), _caso(1.0)]
        motivo_vacio = [_caso(0.0, {"B": (None, "no medible: ")}), _caso(1.0)]
        assert vb.fallos_de_error_maximo(con_motivo), "sin admitir el no medible, no medir cae"
        assert not vb.fallos_de_error_maximo(con_motivo, admite_no_medible=True), "admitido y con su motivo: pasa (la azul se mide en el otro caso)"
        assert vb.fallos_de_error_maximo(sin_motivo, admite_no_medible=True), "admitido, pero tiene que decir por que"
        assert vb.fallos_de_error_maximo(motivo_vacio, admite_no_medible=True), "el prefijo sin nada detras no es un motivo"
        assert vb.fallos_de_error_maximo([_caso(0.0, {"B": (None, "no medible: x")})], admite_no_medible=True), "no vacuidad: admitir el no medible no exime de medir al menos una vez"
        assert vb.fallos_de_error_maximo(buenos, minimo_medidas=4), "no vacuidad: se piden cuatro medidas por capa y hay tres"

    def test_la_franja_de_transito_exige_gris_roja_y_verde_y_deja_a_la_azul_decir_por_que_no(self):
        sin_azul = [_caso(d, {"B": (None, "no medible: la linea tapa el borde de la meseta")}) for d in (-1.0, 0.0, 1.0)] + [_caso(2.0, {})]
        assert not vb.fallos_del_transito(sin_azul), "la azul puede no medirse si dice por que (y se mide en al menos un tercio)"
        assert vb.fallos_del_transito([_caso(d, {"B": (None, "no medible: x")}) for d in (-1.0, 0.0, 1.0)]), "la azul sin medir en TODAS: no vacuidad"
        assert vb.fallos_del_transito([_caso(0.0, {"G": (None, "no medible: x")}), _caso(1.0, {})]), "la verde se mide siempre"
        assert vb.fallos_del_transito([_caso(0.0, {"gris": (None, "no medible: x")}), _caso(1.0, {})]), "y el gris"
        assert vb.fallos_del_transito([_caso(0.0, {"R": (0.2, "Cumple")}), _caso(1.0, {})]), "y la azul y todas se miden a 0.10"

    def test_el_corrimiento_fisico_se_descuenta_solo_si_es_pequeno_y_lo_dio_el_generador(self):
        assert not vb.fallos_del_corrimiento_fisico([_caso(1.0, objetivo=0.91), _caso(-1.0, objetivo=-1.09)])
        assert vb.fallos_del_corrimiento_fisico([_caso(1.0, objetivo=0.80)]), "0.20 mm de corrimiento pasa de 0.12: estaria escondiendo un error"
        assert vb.fallos_del_corrimiento_fisico([_caso(1.0)]), "sin punto medio aparente no hay nada que descontar"
        assert _caso(1.0, objetivo=0.91).esperado_mm == pytest.approx(0.91) and _caso(1.0).esperado_mm == 1.0, "el error se mide contra el objetivo si lo hay y si no, contra la verdad"

    def test_la_elipse_cae_con_un_sesgo_de_0_06_mm_o_un_error_maximo_sobre_el_limite_de_su_giro(self):
        def grupo(giro, errores, modelo="independiente"):
            return {(modelo, giro, 60.0): [_caso(0.0, {c: (e, "Cumple") for c in vb.CAPAS}) for e in errores]}
        simetricos = [-0.3, 0.3] * 4
        assert not vb.fallos_de_la_elipse(grupo(10.0, simetricos)), "errores de +-0.3 mm sin sesgo y bajo el limite de 0.35 de 10 grados"
        assert vb.fallos_de_la_elipse(grupo(10.0, [-0.2, 0.32] * 4)), "sesgo de +0.06 mm con el error maximo (0.32) bajo el limite: cae SOLO por el sesgo"
        assert not vb.fallos_de_la_elipse(grupo(10.0, [-0.24, 0.32] * 4)), "sesgo de +0.04 mm: pasa"
        assert vb.fallos_de_la_elipse(grupo(10.0, [-0.4, 0.4] * 4)), "0.4 mm pasa el limite conocido de 10 grados (0.35) sin ningun sesgo: cae SOLO por el error maximo"
        assert not vb.fallos_de_la_elipse(grupo(20.0, [-0.5, 0.5] * 4)), "y con 20 grados el limite es 0.53"
        assert vb.fallos_de_la_elipse(grupo(20.0, [-0.6, 0.6] * 4))
        assert vb.fallos_de_la_elipse(grupo(15.0, [-0.2, 0.2] * 4, modelo="fisico")), "el analogo fisico se juzga a 0.10"
        assert vb.fallos_de_la_elipse({("independiente", 10.0, 60.0): [_caso(0.0, {"G": (None, "no medible: x")}) for _ in range(5)]}), "sin medidas no hay sesgo que calcular"

    def test_la_mancha_chica_cae_con_una_dispersion_o_un_sesgo_sobre_0_03_mm_en_el_gris_o_con_pocas_medidas(self):
        def con(errores):
            return [_caso(float(i), {"gris": (i + e, "Cumple")}) for i, e in enumerate(errores)]
        assert not vb.fallos_de_la_mancha_chica(con([0.0, 0.02, -0.02, 0.01, -0.01, 0.02, -0.02, 0.0]))
        assert vb.fallos_de_la_mancha_chica(con([0.0, 0.06, -0.06, 0.05, -0.05, 0.06, -0.06, 0.0])), "dispersion de 0.05 mm en el gris pasa el limite de 0.03"
        assert vb.fallos_de_la_mancha_chica(con([0.05] * 8)), "sesgo de 0.05 mm pasa el limite de 0.03"
        assert vb.fallos_de_la_mancha_chica(con([0.0] * 3)), "pocas medidas: no vacuidad"
        assert vb.fallos_de_la_mancha_chica(con([0.0] * 8) + [_caso(9.0, {"R": (None, "no medible")})]), "una capa sin medir tiene que decir por que"

    def test_la_pagina_contra_el_recorte_cae_con_una_diferencia_de_0_03_mm_o_si_una_no_se_mide(self):
        def par(a, b, capa="gris"):
            e1, e2 = vb.Encargo("r", "independiente", 0.5, None, grupo=("recorte", 0.5)), vb.Encargo("p", "independiente", 0.5, None, grupo=("pagina", 0.5))
            return [(e1, _caso(0.5, {capa: (a, "Cumple")})), (e2, _caso(0.5, {capa: (b, "Cumple")}))]
        assert not vb.fallos_de_pagina_contra_recorte(par(0.50, 0.515))
        assert vb.fallos_de_pagina_contra_recorte(par(0.50, 0.53)), "0.03 mm pasa +-0.02"
        assert vb.fallos_de_pagina_contra_recorte(par(0.50, 0.53, capa="B"))
        assert vb.fallos_de_pagina_contra_recorte(par(0.50, None)), "una de las dos sin medir"
        assert vb.fallos_de_pagina_contra_recorte([]), "ningun par"

    def test_la_pagina_rotada_cae_si_se_mide_la_escena_sin_rotar_o_si_cambia_el_sentido_fisico(self):
        bien = _caso(-1.5, sentido="antes de la marca", modelo="fisico")
        assert not vb.fallos_de_la_pagina_rotada([bien])
        # el desfase de la escena (+1.5) en una imagen cuya verdad es -1.5: el error es 3 mm
        sin_rotar = _caso(-1.5, {c: (1.5, "No cumple") for c in vb.CAPAS})
        assert vb.fallos_de_la_pagina_rotada([sin_rotar])
        otro_sentido = _caso(-1.5, sentido="antes de la marca", modelo="fisico")
        otro_sentido.medicion.medidas["gris"] = vb.Medida("ok", -1.5, "No cumple", "despues de la marca")
        assert vb.fallos_de_la_pagina_rotada([otro_sentido]), "rotar la pagina no cambia el sentido fisico (la fuente entra por su cable)"
