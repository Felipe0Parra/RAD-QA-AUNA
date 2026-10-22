"""E.1 + D.1b (PLAN_ANALISIS_PELICULAS_08-10.md; decision del fisico del 20-10-2026: «que se rechace el guardado de la capa que es no medible con el comentario de que es no medible por cualquier
motivo»): la VENTANA no ofrece guardar una capa no medible y dice por que, con las mismas palabras que el guardado.

CAUSA. D.1b puso la regla en el servicio (`svc.motivo_para_no_guardar(resultado, capa)`, la UNICA definicion: None si se puede guardar y, si no, el texto exacto con que `guardar` rechaza). Sin esta
parte de E.1 el fisico podria elegir una capa no medible, pulsar «Guardar» y enterarse DESPUES, con un aviso; o, peor, la ventana tendria su propia regla (`estado == "ok"`) y las dos podrian discrepar.

LO QUE SE GARANTIZA (peliculas medidas el 20-10, `logs/D1b/e1_medir_ventana.log`: la sintetica A de PF.0 cortada por la derecha a u mm del centro del campo de radiacion; todas por el camino del usuario
y contra el MOTOR, que dice cuales capas son medibles):
  1. «Guardar» se ofrece solo con la capa elegida medible y la linea de la regla dice, con el prefijo de la ventana, el texto del servicio TAL CUAL y que mas se puede hacer: la sugerencia nombra EXACTAMENTE
     las capas que la misma funcion da por medibles (la ventana no mueve el menu, no guarda por su cuenta ni ofrece un boton «guardar con...»: PD1, el fisico elige a la vista); con ninguna medible lo
     dice UNA vez. Cuatro escenas: u = 54.5 (las tres medibles, la roja con una penumbra incompleta), 53.0 (la roja no), 51.5 (solo la azul) y 51.0 (ninguna, con el piso no medible); y el sexto clic en la
     esquina con la cortada a 51.0 (ninguna con el piso medible), el sexto clic DENTRO del campo (ninguna) y las causas sin piso (otra resolucion, puntos que no forman el campo).
  2. LA REGLA SE VUELVE A EVALUAR SIN RECALCULAR al cambiar la capa (R, G, R lo enciende y lo apaga con cero llamadas a `analizar`); el cambio de «Piso» y el sexto clic SI recalculan y la reevaluan.
  3. LA VENTANA OBEDECE AL SERVICIO: con `svc.motivo_para_no_guardar` reemplazado por una funcion falsa que solo rechaza la azul, la ventana la obedece (no copia la regla), tambien la sugerencia.
  4. EL TEXTO DE LA LINEA ES EL DEL `PlacaMensualError` que `guardar` lanza con las mismas entradas, y la base queda vacia.
  5. `_al_guardar` llamado directamente con la capa no medible no llama al servicio ni pregunta nada; la pregunta de reemplazo va DESPUES de la regla.
  6. Con un registro el menu queda fijo y la linea vacia; tras Recalcular con una capa no medible el analisis vigente del control no cambia; un registro anterior a D.1b con una capa no medible se abre fijo
     y lo dice. Limpiar deja la linea vacia. Una penumbra incompleta NO vuelve no medible la capa (D1b-D3). Lo que el motor si midio de una capa no medible se sigue viendo (PD3).

Trampa 2 (todo `QMessageBox` y todo cuadro se parcha), Trampa 9 (cierre completo), Trampa 10 (ningun `lru_cache`; las escenas son fixtures de modulo).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt5.QtWidgets import QComboBox, QPushButton

import _placa_mensual_sintetica as gen
from _e1_ayudas import (ADJETIVO, CAPAS, COLOR, TAM, USUARIO, _cursor_limpio, analizada, app, archivo_placa, cargar, clic, con_gid, dialogos, elegir_capa, escaneo_virgen,  # noqa: F401
                        elegir_piso, etiquetas, fabrica, guardada, huella, marcar, parametros, pel, pm, recorrer, resultado_directo, svc, texto_de_la_tabla, ventana, ventana_mod)
from test_d1_guardado_placa_mensual import CAUSAS_NO_MEDIBLES, MENSAJE_NO_MEDIBLE, _auditoria, _causa, _consulta, bd, clics, placa, plantilla, recortada, virgen  # noqa: F401  (fixtures y ayudas de D.1)

PREFIJO = "No se puede guardar: "
NINGUNA = " Ninguna de las tres capas es medible en esta película: de este análisis no se guarda nada, ni la imagen."
ESCENAS = (54.5, 53.0, 51.5, 51.0)
MEDIBLES = {54.5: ("R", "G", "B"), 53.0: ("G", "B"), 51.5: ("B",), 51.0: ()}          # lo medido el 20-10 (logs/D1b/e1_medir_ventana.log): lo comprueba la fixture de escenas con el MOTOR


def _unir(colores):
    """«verde», «verde y azul», «rojo, verde y azul»: como lo dice la sugerencia (escrito aqui a mano: el ancla externa)."""
    return colores[0] if len(colores) == 1 else ", ".join(colores[:-1]) + " y " + colores[-1]


def _sugerencia(guardables):
    """Lo que la linea de la regla agrega tras el texto del servicio, segun cuantas capas sean medibles (el ORACULO de la prueba: escrito a mano desde el plan, no llama a la produccion)."""
    if not guardables:
        return NINGUNA
    if len(guardables) == 1:
        return f" En esta película sí se puede guardar la capa {ADJETIVO[guardables[0]]}; elíjala en el menú «Capa reportada»."
    return f" En esta película sí se pueden guardar: {_unir([COLOR[c] for c in guardables])}; elija una en el menú «Capa reportada»."


def _linea(motivo, guardables):
    return PREFIJO + motivo + "." + _sugerencia(guardables)


def _motivo(resultado, capa):
    """El texto del rechazo, armado con el ESTADO que dice el motor y el formato escrito a mano en D.1 (`MENSAJE_NO_MEDIBLE`): la verdad contra la que se mira la ventana, sin pasar por el servicio."""
    estado = pm().valores_medidos(resultado, capa)["estado"]
    return None if estado == "ok" else MENSAJE_NO_MEDIBLE.format(capa=ADJETIVO[capa], estado=estado)


@pytest.fixture(scope="module")
def escenas(placa, clics, tmp_path_factory):
    """Las cuatro peliculas cortadas por la derecha a u mm del centro de radiacion, escritas en archivos, con lo que el MOTOR dice de cada capa. Las premisas son `assert`, nunca un `skip`: si el motor cambia
    y la escena deja de ser la que las pruebas necesitan, falla aqui diciendo cual era la premisa."""
    cx, _cy = placa.verdad.centro_campo_px
    carpeta = tmp_path_factory.mktemp("e1_escenas")
    salida = {}
    for u in ESCENAS:
        datos = gen.codificar(np.ascontiguousarray(placa.imagen[:, :int(round(cx + u / TAM))]), "png", 600)
        ruta = carpeta / f"cortada_{u}.png"
        ruta.write_bytes(datos)
        resultado, _barrido, _marcas = resultado_directo(datos, clics)
        medibles = tuple(c for c in CAPAS if _motivo(resultado, c) is None)
        assert medibles == MEDIBLES[u], f"premisa de la escena u = {u}: las capas medibles son {MEDIBLES[u]} y el motor dice {medibles}"
        salida[u] = SimpleNamespace(ruta=str(ruta), datos=datos, medibles=medibles, motivos={c: _motivo(resultado, c) for c in CAPAS}, piso_ok=resultado.piso is not None and resultado.piso.estado == "ok",
                                    estado_del_piso=None if resultado.piso is None else resultado.piso.estado)
    assert salida[51.0].piso_ok is False and all(salida[u].piso_ok for u in (54.5, 53.0, 51.5)), "premisa: solo con u = 51.0 el piso automatico no es medible"
    return salida


def _controles(v):
    """Los controles que cambian algo, como (clase, texto): botones, menus y campos editables (lo que la regla no puede aumentar: ningun atajo)."""
    return sorted((type(w).__name__, w.text() if isinstance(w, QPushButton) else "") for w in recorrer(v) if isinstance(w, (QPushButton, QComboBox)))


# ================================================================================================= 1. Guardar se ofrece solo con la capa medible y la linea dice por que

class TestLaVentanaNoOfreceGuardarUnaCapaNoMedible:
    @pytest.mark.parametrize("u", ESCENAS)
    def test_guardar_se_ofrece_solo_con_la_capa_medible_y_la_linea_es_el_texto_del_servicio_con_su_sugerencia(self, fabrica, dialogos, escenas, clics, u):
        escena = escenas[u]
        v = analizada(fabrica(), dialogos, escena.ruta, clics)
        for capa in CAPAS:
            elegir_capa(v, capa)
            medible = capa in escena.medibles
            assert v.boton_guardar.isEnabled() == medible, f"u = {u}, capa {capa}"
            if medible:
                assert v.linea_regla.text() == "" and v.linea_regla.isHidden(), f"u = {u}, capa {capa}: con la capa medible no hay linea"
            else:
                assert v.linea_regla.text() == _linea(escena.motivos[capa], escena.medibles) and not v.linea_regla.isHidden(), f"u = {u}, capa {capa}"

    @pytest.mark.parametrize("u", [53.0, 51.5])
    def test_la_sugerencia_nombra_exactamente_las_capas_medibles_y_la_ventana_no_mueve_el_menu_ni_guarda_por_su_cuenta(self, fabrica, dialogos, escenas, clics, u, monkeypatch):
        llamadas = []
        real = svc().guardar
        monkeypatch.setattr(svc(), "guardar", lambda *a, **k: llamadas.append(1) or real(*a, **k))
        escena = escenas[u]
        v = analizada(fabrica(), dialogos, escena.ruta, clics)
        elegir_capa(v, "R" if u == 53.0 else "G")
        assert escena.medibles == (("G", "B") if u == 53.0 else ("B",))
        asked = v.linea_regla.text()
        assert asked.endswith(_sugerencia(escena.medibles)) and (" verde y azul;" in asked if u == 53.0 else "la capa azul;" in asked)
        assert v.capa_reportada == ("R" if u == 53.0 else "G"), "la ventana no cambia el menu: elige el fisico, a la vista"
        assert not llamadas and not dialogos.llamadas and not v.boton_guardar.isEnabled() and v.estado == "analizada"
        assert _controles(v) == _controles(fabrica()), "ningun boton ni menu mas que sin la regla: no hay un atajo «guardar con...»"

    def test_con_ninguna_capa_medible_lo_dice_una_sola_vez_sin_atajos_y_con_el_piso_no_medible_ofrece_lo_de_a3(self, fabrica, dialogos, escenas, clics):
        v = analizada(fabrica(), dialogos, escenas[51.0].ruta, clics)
        assert "Puede tomar el piso con «Marcar película sin irradiar» o con una película virgen («Película virgen...»)." in v.etiqueta_piso.text(), "con el piso no medible se ofrece la virgen y el sexto clic"
        assert _controles(v) == _controles(fabrica()), "el censo de controles es el de una ventana sin la regla: ningun atajo"
        for capa in CAPAS:
            elegir_capa(v, capa)
            assert v.linea_regla.text() == _linea(escenas[51.0].motivos[capa], ()) and v.linea_regla.text().count("Ninguna de las tres capas") == 1
            assert v.linea_regla.text().count("la capa " + ADJETIVO[capa] + " no es medible") == 1, "el texto del servicio va una vez, no tres textos iguales"
            assert not v.boton_guardar.isEnabled()

    def test_una_penumbra_incompleta_no_vuelve_no_medible_la_capa(self, fabrica, dialogos, escenas, clics):
        v = analizada(fabrica(), dialogos, escenas[54.5].ruta, clics)
        elegir_capa(v, "R")
        assert v.boton_guardar.isEnabled() and v.linea_regla.isHidden()
        avisos = [fila[10] for fila in texto_de_la_tabla(v.tabla_perfiles) if fila[0] == "Capa roja"]
        assert any("incompleta: el perfil llega al borde de la película antes del 20 %" in a for a in avisos), "la penumbra incompleta se VE como aviso y Guardar se ofrece"

    def test_lo_que_el_motor_si_midio_de_una_capa_no_medible_se_sigue_viendo_sin_decir_se_guarda(self, fabrica, dialogos, escenas, clics):
        v = analizada(fabrica(), dialogos, escenas[53.0].ruta, clics)
        elegir_capa(v, "R")
        filas = {(f[0], f[1]): f for f in texto_de_la_tabla(v.tabla_perfiles)}
        cruzada, interna = filas[("Capa roja", "crossplane")], filas[("Capa roja", "inplane")]
        assert cruzada[2].startswith("no medible: perfil crossplane: no se encuentra el borde derecho") and cruzada[3] == "sin dato"
        assert interna[2] == "ok" and interna[3] != "sin dato", "el eje que si cruzo el 50 % se sigue viendo"
        assert cruzada[11] == interna[11] == "no se guarda: no es medible", "la fila de la capa elegida dice que NO se guarda, nunca «se guarda» (corolario 6)"
        assert all(f[11] == "" for k, f in filas.items() if k[0] != "Capa roja")
        assert v.nota_pestana1.text() == escenas[53.0].motivos["R"], "la nota de la pestana 1 es, en vez de la frase de siempre, el texto del servicio tal cual"
        assert "se guarda" not in v.nota_pestana1.text().replace("no se guarda", "")
        elegir_capa(v, "G")
        assert [f[11] for f in texto_de_la_tabla(v.tabla_perfiles)] == ["", "", "se guarda", "se guarda", "", "", "", ""], "con la verde, la fila de la verde dice se guarda y la de la roja ya no dice nada"
        assert v.nota_pestana1.text() == "Estos son los desfases del perfil de grises. Lo que se guarda y se imprime es lo de la capa verde, que se ve en la pestaña 3."

    def test_con_el_piso_no_medible_la_ventana_dice_su_motivo_y_ofrece_la_virgen_y_el_sexto_clic(self, fabrica, dialogos, escenas, clics):
        v = analizada(fabrica(), dialogos, escenas[51.0].ruta, clics)
        assert not escenas[51.0].estado_del_piso.endswith("."), "premisa: el motivo del motor no trae punto final"
        assert v.etiqueta_piso.text() == "Piso: " + escenas[51.0].estado_del_piso + ". Puede tomar el piso con «Marcar película sin irradiar» o con una película virgen («Película virgen...»).", \
            "E1-R2-PROD-02: la frase del motivo se cierra con su punto antes de la que ofrece la virgen y el sexto clic (EDITADA en la ronda 2: esperaba las dos frases pegadas sin punto)"
        assert not v.boton_guardar.isEnabled() and v.estado == "analizada"

    def test_el_sexto_clic_en_la_esquina_con_la_pelicula_cortada_deja_el_piso_medible_y_ninguna_capa(self, fabrica, dialogos, escenas, clics):
        v = fabrica()
        cargar(v, dialogos, escenas[51.0].ruta)
        v.boton_sexto.click()
        clic(v, 87, 87)
        marcar(v, clics)
        assert v.estado == "analizada" and v._resultado.piso.estado == "ok" and v._resultado.piso.origen == "manual" and v.modo_del_piso == "punto_manual"
        assert "Puede tomar el piso con" not in v.etiqueta_piso.text(), "con el piso medible no se ofrece lo del piso: lo que falla es otra cosa"
        assert _controles(v) == _controles(fabrica())
        resultado, _b, _m = resultado_directo(escenas[51.0].datos, clics, "punto_manual", (87.0, 87.0))
        assert [_motivo(resultado, c) is None for c in CAPAS] == [False, False, False], "premisa: con el piso medible ninguna capa se mide en esta pelicula"
        for capa in CAPAS:
            elegir_capa(v, capa)
            assert v.linea_regla.text() == _linea(_motivo(resultado, capa), ()) and not v.boton_guardar.isEnabled()

    def test_el_sexto_clic_dentro_del_campo_apaga_guardar_con_el_texto_del_piso(self, fabrica, dialogos, placa, archivo_placa, clics):
        cx, cy = placa.verdad.centro_campo_px
        dentro = (float(round(cx + 20 / TAM)), float(round(cy + 20 / TAM)))
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        assert v.boton_guardar.isEnabled(), "antes del sexto clic la pelicula entera se mide"
        v.boton_sexto.click()
        clic(v, *dentro)
        assert v.estado == "analizada" and not v.boton_guardar.isEnabled() and v.modo_del_piso == "punto_manual"
        resultado, _b, _m = resultado_directo(placa.datos, clics, "punto_manual", dentro)
        assert resultado.piso.estado.startswith("no medible: el punto marcado no tiene el nivel de una película sin irradiar")
        assert v.linea_regla.text() == _linea(_motivo(resultado, "G"), ()) and "el punto marcado no tiene el nivel de una película sin irradiar" in v.linea_regla.text()
        assert v.etiqueta_piso.text().startswith("Piso: no medible: el punto marcado no tiene el nivel") and "Puede tomar el piso con" in v.etiqueta_piso.text()
        assert _controles(v) == _controles(fabrica())

    def test_una_pelicula_que_declara_otra_resolucion_no_se_ofrece(self, fabrica, dialogos, placa, clics, tmp_path):
        ruta = tmp_path / "a_300.png"
        ruta.write_bytes(gen.codificar(placa.imagen, "png", 300))
        v = analizada(fabrica(), dialogos, str(ruta), clics)
        resultado, _b, _m = resultado_directo(gen.codificar(placa.imagen, "png", 300), clics)
        assert resultado.piso is None and not v.boton_guardar.isEnabled()
        assert v.linea_regla.text() == _linea(_motivo(resultado, "G"), ()) and "no hay escala en milímetros" in v.linea_regla.text()

    def test_unos_puntos_que_no_forman_el_campo_no_se_ofrecen(self, fabrica, dialogos, archivo_placa):
        raros = [(10, 10), (20, 20), (30, 30), (40, 40), (50, 50)]
        v = analizada(fabrica(), dialogos, archivo_placa, raros)
        resultado, _b, _m = resultado_directo(open(archivo_placa, "rb").read(), raros)
        assert not v.boton_guardar.isEnabled() and v.linea_regla.text() == _linea(_motivo(resultado, "G"), ()) and "los puntos no forman el campo" in v.linea_regla.text()

    def test_la_pelicula_cortada_con_la_virgen_como_piso_deja_la_roja_sin_guardar_y_ofrece_la_verde_y_la_azul(self, fabrica, dialogos, recortada, tmp_path, bd, escaneo_virgen):
        datos, puntos = recortada
        ruta = tmp_path / "recortada.png"
        ruta.write_bytes(datos)
        pel().guardar_referencia_virgen(escaneo_virgen.referencia, os.path.dirname(bd), escaneo_virgen.datos, USUARIO)
        v = analizada(fabrica(), dialogos, str(ruta), puntos)
        assert not v.boton_guardar.isEnabled() and v._resultado.piso.estado != "ok", "premisa: con el piso automatico esta pelicula no se mide (sin pelicula en las esquinas)"
        elegir_piso(v, "virgen")
        resultado, _b, _m = resultado_directo(datos, puntos, "virgen", None, escaneo_virgen.referencia)
        assert tuple(c for c in CAPAS if _motivo(resultado, c) is None) == ("G", "B"), "premisa (D.1b): con la virgen la roja pierde sus bordes y la verde y la azul se miden"
        elegir_capa(v, "R")
        assert not v.boton_guardar.isEnabled() and v.linea_regla.text() == _linea(_motivo(resultado, "R"), ("G", "B"))
        elegir_capa(v, "B")
        assert v.boton_guardar.isEnabled() and v.linea_regla.isHidden()


# ================================================================================================= 2. la regla se vuelve a evaluar sin recalcular

class TestLaReglaSeVuelveAEvaluar:
    def test_cambiar_la_capa_enciende_y_apaga_guardar_sin_recalcular_y_cambiar_el_piso_si_recalcula(self, fabrica, dialogos, escenas, clics, monkeypatch):
        medidas, reglas = [], []
        real_analizar, real_regla = pm().analizar, svc().motivo_para_no_guardar
        monkeypatch.setattr(pm(), "analizar", lambda *a, **k: medidas.append(k.get("modo_piso")) or real_analizar(*a, **k))
        monkeypatch.setattr(svc(), "motivo_para_no_guardar", lambda r, c: reglas.append(c) or real_regla(r, c))
        v = analizada(fabrica(), dialogos, escenas[53.0].ruta, clics)
        assert medidas == ["automatico"] and v.boton_guardar.isEnabled()
        medidas_antes = len(medidas)
        for capa, enciende in (("R", False), ("G", True), ("R", False), ("B", True)):
            reglas.clear()
            elegir_capa(v, capa)
            assert v.boton_guardar.isEnabled() == enciende and reglas, f"{capa}: la regla se vuelve a preguntar al servicio"
        assert len(medidas) == medidas_antes, "ningun cambio de capa recalcula"
        v.boton_sexto.click()
        clic(v, 87, 87)
        assert medidas[-1] == "punto_manual" and len(medidas) == medidas_antes + 1, "el sexto clic si recalcula"

    def test_la_ventana_obedece_al_servicio_y_no_copia_la_regla(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        """Con una funcion falsa que solo rechaza la azul (la pelicula entera las mide las tres), la ventana la obedece: ni el habilitado ni el texto ni la sugerencia salen de otra regla."""
        monkeypatch.setattr(svc(), "motivo_para_no_guardar", lambda r, c: "texto falso de prueba" if c == "B" else None)
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        assert v.boton_guardar.isEnabled() and v.linea_regla.isHidden()
        elegir_capa(v, "B")
        assert not v.boton_guardar.isEnabled() and v.linea_regla.text() == _linea("texto falso de prueba", ("R", "G"))
        elegir_capa(v, "G")
        assert v.boton_guardar.isEnabled() and v.linea_regla.text() == ""

    def test_un_texto_distinto_del_servicio_se_dice_tal_cual_con_su_prefijo(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        monkeypatch.setattr(svc(), "motivo_para_no_guardar", lambda r, c: "OTRO TEXTO" if c == "R" else None)
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_capa(v, "R")
        assert v.linea_regla.text().startswith(PREFIJO + "OTRO TEXTO.") and v.nota_pestana1.text() == "OTRO TEXTO"

    def test_un_texto_del_servicio_que_ya_trae_su_punto_no_se_cierra_con_otro(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        """E1-R2-PROD-03 (la misma clase): la linea de la regla es el texto del servicio TAL CUAL; si termina en punto, la ventana no agrega otro."""
        monkeypatch.setattr(svc(), "motivo_para_no_guardar", lambda r, c: "OTRO TEXTO." if c == "R" else None)
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_capa(v, "R")
        assert v.linea_regla.text() == PREFIJO + "OTRO TEXTO." + _sugerencia(("G", "B")) and ".." not in v.linea_regla.text() and v.nota_pestana1.text() == "OTRO TEXTO."

    def test_al_guardar_llamado_directamente_con_la_capa_no_medible_no_llama_al_servicio_ni_pregunta(self, fabrica, dialogos, escenas, clics, monkeypatch):
        llamadas = []
        real = svc().guardar
        monkeypatch.setattr(svc(), "guardar", lambda *a, **k: llamadas.append(1) or real(*a, **k))
        v = analizada(fabrica(), dialogos, escenas[53.0].ruta, clics)
        elegir_capa(v, "R")
        assert not v.boton_guardar.isEnabled()
        v._al_guardar()                                                  # el boton esta apagado, pero el manejador se puede llamar solo
        assert not llamadas and not dialogos.llamadas and v.estado == "analizada" and v.linea_regla.text() == _linea(escenas[53.0].motivos["R"], ("G", "B"))

    def test_la_pregunta_de_reemplazo_va_despues_de_la_regla(self, fabrica, dialogos, escenas, clics, bd):
        v = fabrica()
        analizada(v, dialogos, escenas[53.0].ruta, clics)
        v.boton_guardar.click()
        assert v.estado == "registro"
        v.boton_recalcular.click()
        marcar(v, clics)
        dialogos.llamadas.clear()
        elegir_capa(v, "R")
        v._al_guardar()
        assert not dialogos.de("question") and v.estado == "analizada", "nunca se pregunta «¿reemplazar?» por algo que no se va a guardar"
        elegir_capa(v, "G")
        v.boton_guardar.click()
        assert len(dialogos.de("question")) == 1

    def test_un_rechazo_de_guardar_con_el_mismo_texto_de_la_linea_y_la_base_vacia(self, fabrica, dialogos, escenas, clics, bd):
        """El texto de la linea es el del `PlacaMensualError` que `guardar` lanza con las mismas entradas (la regla es una) y esa llamada no escribe nada."""
        v = analizada(fabrica(), dialogos, escenas[53.0].ruta, clics)
        elegir_capa(v, "R")
        with pytest.raises(svc().PlacaMensualError) as error:
            svc().guardar(v.ref_de_prueba, USUARIO, escenas[53.0].datos, "cortada_53.0.png", [m.clic for m in v.marcas], parametros(), "R", "automatico")
        assert PREFIJO + str(error.value) + "." in v.linea_regla.text() and str(error.value) == escenas[53.0].motivos["R"]
        assert not _consulta(bd, "SELECT 1 FROM analisis_placa_mensual") and not _auditoria(bd)


# ================================================================================================= 3. registros, Limpiar

class TestConUnRegistro:
    def test_con_un_registro_el_menu_queda_fijo_y_la_linea_vacia_y_tras_recalcular_con_una_capa_no_medible_el_vigente_no_cambia(self, fabrica, dialogos, escenas, archivo_placa, clics, bd):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)          # la pelicula entera, con la verde
        assert not v.selector_capa.isEnabled() and v.linea_regla.isHidden() and v.linea_regla.text() == ""
        assert not v.boton_guardar.isEnabled(), "con un registro «Guardar» queda apagado por ser un registro (la verde es medible: la regla sola lo dejaria encendido)"
        vigente = svc().leer(v.ref_de_prueba)
        v.boton_recalcular.click()
        cargar(v, dialogos, escenas[53.0].ruta)                          # otra pelicula (la cortada a 53.0 mm): la roja no se mide
        marcar(v, clics)
        elegir_capa(v, "R")
        assert not v.boton_guardar.isEnabled() and v.linea_regla.text() == _linea(escenas[53.0].motivos["R"], ("G", "B"))
        v.boton_guardar.click()
        assert svc().leer(v.ref_de_prueba) == vigente and len(_auditoria(bd)) == 1 and not dialogos.de("question"), "el servicio no se llama y el analisis vigente no se toca"

    def test_un_registro_anterior_a_d1b_con_una_capa_no_medible_se_abre_fijo_y_lo_dice(self, fabrica, dialogos, escenas, clics, monkeypatch):
        """Fabricado quitando la regla en un guardado (como en las pruebas de D.1): una capa roja no medible, guardada con sus numeros vacios. Al abrirlo se recalcula, el menu queda fijo en ella, Guardar apagado,
        la linea de la regla vacia (no hay que decidir nada: es un registro) y una linea de la etiqueta dice que en lo recalculado ya no es medible."""
        ref = fabrica.control()
        with monkeypatch.context() as m:
            m.setattr(svc(), "motivo_para_no_guardar", lambda r, c: None)
            svc().guardar(ref, USUARIO, escenas[53.0].datos, "cortada_53.0.png", clics, parametros(), "R", "automatico")
        dialogos.llamadas.clear()
        w = fabrica(ref=ref)
        assert w.estado == "registro" and w.capa_reportada == "R" and not w.selector_capa.isEnabled() and not w.boton_guardar.isEnabled() and w.linea_regla.isHidden() and not dialogos.llamadas
        assert f"En lo recalculado la capa guardada ya no es medible: {escenas[53.0].motivos['R']}." in w.etiqueta_registro.text()
        filas = {(f[0], f[1]): f for f in texto_de_la_tabla(w.tabla_perfiles)}
        assert filas[("Capa roja", "crossplane")][11] == filas[("Capa roja", "inplane")][11] == "guardada; en lo recalculado no es medible", "nunca afirma que se guarda lo que el guardado rechaza"
        assert w.nota_pestana1.text() == "Estos son los desfases del perfil de grises. Lo guardado y lo que imprime el PDF es la capa roja, que se ve en la pestaña 3."

    def test_en_lo_recalculado_el_motivo_que_ya_trae_su_punto_no_se_cierra_con_otro(self, fabrica, dialogos, escenas, clics, monkeypatch):
        """E1-R2-PROD-03 (la misma clase, otro sitio): la linea «En lo recalculado la capa guardada ya no es medible: <motivo>» tampoco duplica el punto del motivo."""
        ref = fabrica.control()
        with monkeypatch.context() as m:
            m.setattr(svc(), "motivo_para_no_guardar", lambda r, c: None)
            svc().guardar(ref, USUARIO, escenas[53.0].datos, "cortada_53.0.png", clics, parametros(), "R", "automatico")
        monkeypatch.setattr(svc(), "motivo_para_no_guardar", lambda r, c: "motivo de prueba." if c == "R" else None)
        w = fabrica(ref=ref)
        assert w.estado == "registro" and "En lo recalculado la capa guardada ya no es medible: motivo de prueba.\n" in w.etiqueta_registro.text() + "\n" and ".." not in w.etiqueta_registro.text()

    def test_limpiar_deja_la_linea_vacia_y_la_ventana_igual_a_una_recien_creada(self, fabrica, dialogos, escenas, clics):
        v = fabrica()
        nueva = huella(v)
        analizada(v, dialogos, escenas[51.0].ruta, clics)
        assert not v.linea_regla.isHidden() and v.linea_regla.text()
        v.boton_limpiar.click()
        assert v.linea_regla.isHidden() and v.linea_regla.text() == "" and v.nota_pestana1.text() == "" and huella(v) == nueva

    def test_recalcular_y_cargar_otra_imagen_vacian_la_linea_de_la_regla(self, fabrica, dialogos, escenas, clics, archivo_placa):
        """Sin analisis no hay nada que decir sobre guardar: la linea de la regla se vacia al Recalcular y al cargar otra imagen (Limpiar la vacia ademas por otro camino, `refrescar`, y no distingue)."""
        v = analizada(fabrica(), dialogos, escenas[51.0].ruta, clics)
        assert not v.linea_regla.isHidden() and v.linea_regla.text()
        v.boton_recalcular.click()
        assert v.estado == "imagen" and v.linea_regla.isHidden() and v.linea_regla.text() == ""
        marcar(v, clics)
        assert v.estado == "analizada" and v.linea_regla.text(), "premisa: el analisis nuevo vuelve a escribir la linea"
        cargar(v, dialogos, archivo_placa)
        assert v.estado == "imagen" and v.linea_regla.isHidden() and v.linea_regla.text() == ""


# ================================================================================================= 4. cada causa de `CAUSAS_NO_MEDIBLES` (la lista de D.1b) por la ventana

# E1-REV1-PRU-04 (ronda 1 de la revision). El protocolo del plan manda probar la regla en la ventana «con las causas de `CAUSAS_NO_MEDIBLES` de `test_d1`»; las pruebas de arriba usan sus propias escenas (los cortes
# a u mm, el sexto clic dentro del campo, otra resolucion, puntos que no forman el campo) y dos causas de la lista no pasaban por la ventana: «piso fuera del rango esperado» y «modo virgen sin pelicula
# virgen». Aqui se recorre la lista ENTERA (importada de D.1: una causa que se agregue alla se prueba aca sola) mas las tres escenas que D.1b midio aparte, cada una con los argumentos que D.1 usa para
# `guardar` (`_causa`): la ventana ofrece «Guardar» exactamente cuando `guardar` guarda y, si no, dice el texto con que `guardar` rechaza.
CAUSAS_POR_LA_VENTANA = CAUSAS_NO_MEDIBLES + ("puntos que no forman el campo", "otra resolucion declarada", "medible")


class TestCadaCausaDeD1bPorLaVentana:
    def test_la_lista_de_causas_es_la_de_d1_y_trae_las_dos_que_las_demas_pruebas_no_recorrian(self):
        assert len(CAUSAS_NO_MEDIBLES) >= 5 and {"piso fuera del rango esperado", "modo virgen sin pelicula virgen"} <= set(CAUSAS_NO_MEDIBLES)
        assert len(set(CAUSAS_POR_LA_VENTANA)) == len(CAUSAS_POR_LA_VENTANA)

    @pytest.mark.parametrize("causa", CAUSAS_POR_LA_VENTANA)
    def test_la_ventana_tiene_la_misma_regla_y_el_mismo_texto_que_guardar_en_cada_causa(self, causa, fabrica, dialogos, placa, clics, recortada, virgen, tmp_path, bd, monkeypatch):
        capa, modo, cambios = _causa(causa, placa, recortada)
        datos, puntos, punto = cambios.get("datos", placa.datos), cambios.get("puntos", clics), cambios.get("punto_manual")
        referencia = cambios.get("referencia_virgen", virgen) if modo == "virgen" else None
        if "parametros" in cambios:
            # el rango esperado del piso que ninguna pelicula de esta placa cumple: la ventana mide con los parametros de fabrica del motor, asi que es el motor quien cambia (y el oraculo, que los copia, tambien)
            monkeypatch.setitem(pm().VALORES_DE_LA_GEOMETRIA, "piso_esperado", cambios["parametros"]["piso_esperado"])
        if referencia is not None:
            pel().guardar_referencia_virgen(referencia, os.path.dirname(bd), None, USUARIO)
        ruta = tmp_path / "causa.png"
        ruta.write_bytes(datos)
        llamadas = []
        real = svc().guardar
        monkeypatch.setattr(svc(), "guardar", lambda *a, **k: llamadas.append(1) or real(*a, **k))
        v = fabrica()
        cargar(v, dialogos, str(ruta))
        marcar(v, puntos)
        assert v.estado == "analizada", (causa, v.estado)
        if punto is not None:
            v.boton_sexto.click()
            clic(v, *punto)
        if modo == "virgen":
            elegir_piso(v, "virgen")                 # sin referencia el item esta apagado (no se elige con el raton); por codigo se llega: la ventana no debe volver sola al automatico
        elegir_capa(v, capa)
        assert v.estado == "analizada" and v.modo_del_piso == modo and v.capa_reportada == capa, (causa, v.estado, v.modo_del_piso, v.capa_reportada)
        resultado, _b, _m = resultado_directo(datos, puntos, modo, punto, referencia)
        motivo = _motivo(resultado, capa)
        guardables = tuple(c for c in CAPAS if _motivo(resultado, c) is None)
        assert (motivo is None) == (causa == "medible"), f"premisa: el motor dice que la capa {capa} es medible solo en la escena «medible» ({causa}: {motivo})"
        if motivo is None:
            assert v.boton_guardar.isEnabled() and v.linea_regla.isHidden() and v.linea_regla.text() == ""
            v.boton_guardar.click()
            assert v.estado == "registro" and len(llamadas) == 1 and svc().leer(v.ref)["estado"] == "ok" and svc().leer(v.ref)["capa"] == capa
            return
        assert not v.boton_guardar.isEnabled() and not v.linea_regla.isHidden()
        assert v.linea_regla.text() == _linea(motivo, guardables), causa
        with pytest.raises(svc().PlacaMensualError) as error:
            svc().guardar(fabrica.control(), USUARIO, datos, "causa.png", puntos, parametros(), capa, modo, punto_manual=punto, referencia_virgen=referencia)
        assert str(error.value) == motivo and v.linea_regla.text().startswith(PREFIJO + str(error.value) + "."), "el texto de la linea es el del rechazo de `guardar` con las mismas entradas"
        llamadas.clear()
        dialogos.llamadas.clear()
        v._al_guardar()                                                  # el boton esta apagado, pero el manejador se puede llamar solo
        assert not llamadas and not dialogos.llamadas and v.estado == "analizada"
        assert not _consulta(bd, "SELECT 1 FROM analisis_placa_mensual") and not _auditoria(bd)


# ================================================================================================= 5. lo que la ventana dice del piso y de los barridos cuando una capa no se pudo medir (ronda 2 de la revision)

OFRECE_EL_PISO = "Puede tomar el piso con «Marcar película sin irradiar» o con una película virgen («Película virgen...»)."


class TestLaLineaDelPisoCierraSusFrases:
    @pytest.mark.parametrize("caso", ["diminuta", "blanca", "negra"])
    def test_con_el_piso_no_medible_la_frase_del_motivo_termina_en_un_signo_final_antes_de_lo_que_se_ofrece(self, fabrica, dialogos, tmp_path, caso):
        """E1-R2-PROD-02 (ronda 2 de la revision). `texto_breve_del_piso` da «Piso: <motivo>» sin punto final y la ventana le pegaba « Puede tomar el piso con...» directamente («...fuera del campo Puede tomar...»).
        Tres motivos de formas distintas: uno corto, uno que termina en parentesis y uno largo con parentesis dentro."""
        forma, nivel = {"diminuta": ((40, 60, 3), 200), "blanca": ((1200, 1500, 3), 255), "negra": ((1200, 1500, 3), 0)}[caso]
        ruta = tmp_path / f"{caso}.png"
        ruta.write_bytes(gen.codificar(np.full(forma, nivel, np.uint8), "png", 600))
        v = fabrica()
        cargar(v, dialogos, str(ruta))
        alto, ancho = v._forma
        marcar(v, [(ancho * 0.2, alto * 0.2), (ancho * 0.8, alto * 0.2), (ancho * 0.5, alto * 0.5), (ancho * 0.8, alto * 0.8), (ancho * 0.2, alto * 0.8)])
        assert v.estado == "analizada" and v._resultado.piso is not None and v._resultado.piso.estado.startswith("no medible"), "premisa: el piso no se pudo medir"
        texto = v.etiqueta_piso.text()
        assert texto.startswith("Piso: no medible: ") and texto.count("Puede tomar el piso con") == 1 and texto.endswith(" " + OFRECE_EL_PISO), texto
        antes = texto[:len(texto) - len(OFRECE_EL_PISO) - 1]
        assert antes[-1] in ".!?" and ".." not in antes, f"la frase del motivo termina en un signo final: ...{antes[-50:]!r}"
        assert antes.rstrip(".") == "Piso: " + v._resultado.piso.estado.rstrip("."), "y es el motivo del motor tal cual"

    def test_la_frase_de_una_capa_sin_piso_tambien_se_cierra_antes_de_lo_que_sigue(self, fabrica, dialogos, archivo_placa, clics):
        """E1-R2-PROD-02, el otro camino: el piso se midio pero esa capa no (el piso no llega a 10 niveles de la meseta); `texto_breve_del_piso` da «Piso (capa verde): no medible: ...» sin punto final y lo
        que sigue (la comparacion con la virgen, los avisos) iba pegado. Se fabrica la capa sin piso y un aviso, porque la sintetica no produce ninguno."""
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        piso = v._resultado.piso
        sin_piso = dataclasses.replace(piso.capas["G"], estado="no medible: el piso no es al menos 10 niveles más claro que la meseta")
        v._resultado = dataclasses.replace(v._resultado, piso=dataclasses.replace(piso, capas={**piso.capas, "G": sin_piso}, avisos=("Un aviso de prueba.",)))
        v._aplicar_la_regla()
        assert v.etiqueta_piso.text() == "Piso (capa verde): no medible: el piso no es al menos 10 niveles más claro que la meseta. Un aviso de prueba."


ROTULOS_DEL_BARRIDO = {"central": "corte central, banda 0", "media": "media, discontinua", "mediana": "mediana, punteada"}


class TestLaLeyendaDeLosBarridosDiceLoQueDibuja:
    @pytest.mark.parametrize("u", ESCENAS)
    def test_cada_elemento_que_el_barrido_dibuja_sale_una_sola_vez_en_la_leyenda_sea_cual_sea_la_primera_capa_que_lo_dibuja(self, fabrica, dialogos, escenas, clics, u):
        """E1-R2-PROD-01 (ronda 2 de la revision). Las etiquetas «corte central, banda 0», «media, discontinua» y «mediana, punteada» se le ponian solo al trazo de la capa ROJA; en las peliculas cortadas (que el
        fisico dijo que pueden ser lo habitual) la roja no se mide y la figura dibujaba los rombos, las medias y las medianas de las otras capas SIN explicarlos (PD1: cada grafica dibuja Y explica todo lo que se
        uso). Ahora cada elemento lleva su etiqueta en el primer trazo que lo dibuja: UNA vez por eje, con la roja o sin ella."""
        v = analizada(fabrica(), dialogos, escenas[u].ruta, clics)
        ejes = v._fig_barridos.axes
        assert len(ejes) == 2
        for ax, eje in zip(ejes, ("crossplane", "inplane")):
            textos = etiquetas(ax)
            for clave, rotulo in ROTULOS_DEL_BARRIDO.items():
                dibujado = bool(con_gid(ax, f"barrido:{clave}:"))
                assert textos.count(rotulo) == (1 if dibujado else 0), (u, eje, clave, textos)

    @pytest.mark.parametrize("u,sin_centro", [(53.0, ("R",)), (51.5, ("R", "G", "gris"))])
    def test_con_las_primeras_capas_sin_medir_el_eje_crossplane_dibuja_las_otras_y_la_leyenda_las_explica(self, fabrica, dialogos, escenas, clics, u, sin_centro):
        """Las escenas donde el defecto se ve: en el crossplane de la pelicula cortada a 53.0 mm la roja no tiene corte central y en la de 51.5 mm solo lo tiene la azul."""
        v = analizada(fabrica(), dialogos, escenas[u].ruta, clics)
        ax = v._fig_barridos.axes[0]
        for capa in (*CAPAS, "gris"):
            for clave in ROTULOS_DEL_BARRIDO:
                assert bool(con_gid(ax, f"barrido:{clave}:{capa}")) == (capa not in sin_centro), (u, capa, clave)
        assert set(ROTULOS_DEL_BARRIDO.values()) <= set(etiquetas(ax)), etiquetas(ax)

