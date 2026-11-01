"""CD.7 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-92, DC9, DC10, DC11): LA VENTANA MENSUAL EN DOSIS. El boton «Ver en dosis» y el boton «Curva de dosis...».

CAUSA: la ventana no ofrecia ninguna curva y dibujaba solo en netOD. Lo pidio el fisico: «segun esa curva fijar el rango de los perfiles mostrados», y el 28-10 (DA-92) un boton que pase TODAS las pestanas a
dosis salvo la imagen de la pelicula con lo dibujado encima, que arranque siempre en netOD y que solo se pueda pulsar si se cumplen las condiciones (la regla del motor, CD.6).

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale de la ventana (la placa sintetica de la verdad en dosis de CD.6, la curva de CD.3 hecha con piezas de la MISMA respuesta, el motor directamente):
  EL CAMINO DE UNA PERSONA: abre la placa, marca los cinco puntos, ve la netOD con el boton apagado y la curva en uso en su linea; pulsa «Ver en dosis»: los perfiles en cGy con el eje FIJO de la curva, la
    pestana «Capas» en dosis con la misma escala, los barridos en dosis, la tabla con la dosis de la meseta y su U (la verdad: 100 x 99 mm y 300 cGy); apaga el boton: la netOD de antes, identica.
  LA REGLA: el boton se habilita con `se_puede_pasar_a_dosis` sobre la capa reportada; sin curva, con una guia, con otra cadena o con el piso de las esquinas queda gris y su linea y su ayuda dicen el motivo
    (la ayuda, la regla entera); cambiar la capa reportada la vuelve a evaluar y, si ya no se cumple, la vista vuelve a netOD.
  LA MEMORIA: el analisis en dosis se calcula UNA vez (con el cursor de espera) y se descarta al cambiar la pelicula, los puntos, el piso o la curva.
  LO QUE LO DEJA APAGADO: «Limpiar», abrir un registro (aunque haya una curva vigente valida: un registro abre en netOD y, hasta CD.6b, se guardo sin dosis) y «Guardar» (lo guardado es la netOD).
  «CURVA DE DOSIS...»: abre la ventana de CD.5 con el OBJETO de la sesion (H-CD5-7) y, al cerrarla, la curva y la regla se vuelven a evaluar.
  EL DIBUJO (sin Qt): el eje de la dosis sale solo de la curva; una capa no medible en dosis no se pinta en otra base; la tabla gana sus dos columnas solo en dosis; el parametro 42 tiene su frase en el pie.
  EL AJUSTE DEL 31-10 (pedidos del fisico, 22:20, 22:38 y 22:50): las cinco lineas explicativas fuera de la ventana y en el cuadro «Info» (no modal, a la derecha de «Guardar»), el alto de la
    imagen y de las pestanas que no cambia al marcar ni al analizar, la tabla de la CAPA REPORTADA al lado de la imagen con los datos importantes (la capa, el FWHM por corte, los dos desfases de centro,
    los desfases por lado, la meseta en netOD o en dosis, las penumbras y los largos por debajo del 20 %: `filas_de_la_capa_reportada`, la misma que usara el PDF), el largo por debajo del 20 % de cada
    lado hasta el piso en el motor (aditivo, con su parametro 43; segunda pasada del 01-11), ningun perfil gris en ninguna pestana y la cuadratura contra un cuadrado de 100 mm de lado (antes, la media
    de los lados medidos). Clases `TestElCuadroInfo`, `TestElAltoNoCambia`, `TestLaTablaDeLaImagen`, `TestElLargoBajoElVeinte`, `TestSinElGris` y `TestLaCuadraturaContra100`.
Lo que NO se prueba aqui y si en la compuerta del anexo (`cd7_diferencial.py`): con el boton apagado la ventana es IDENTICA a la del commit de CD.6 (la huella), salvo lo nombrado (los botones nuevos y su
linea, el cuadro «Info» con lo que se mudo a el, el gris retirado, la tabla de la pestana 1 y la columna del cuadrado perfecto).

Rojo contra el commit de CD.6: la ventana no tiene `boton_dosis` ni el dibujo `eje_de_la_dosis`: las pruebas caen con su error. Las pruebas importan la produccion POR PRUEBA (`_e1_ayudas`).
Lo caro (la placa de 600 ppp a 16 bits, unos 20 s, y la curva) es una fixture de modulo; cada ventana es de su prueba.
"""
import ast
import copy
import dataclasses
import gc
import math
import types
from pathlib import Path

import numpy as np
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QHideEvent
from PyQt5.QtWidgets import QApplication

import _piezas_de_calibracion_sinteticas as gp
import _placa_mensual_sintetica as gen
from _e1_ayudas import (_cursor_limpio, _virgen_sintetica, app, cerrar, clic, dialogos, dibujo_mod, fabrica, huella, pel, pm, sin_simbolos, svc, texto_de_la_tabla,  # noqa: F401
                        todos_los_textos, ventana_mod)
from test_d1_guardado_placa_mensual import bd, plantilla  # noqa: F401  (fixtures de D.1)

RAIZ = Path(__file__).resolve().parent.parent
FECHA = "2026-10-31"
DOSIS_MESETA = 300.0
RESP = {"R": gp.RespuestaDevic(700.0, 3300.0, 2.06), "G": gp.RespuestaDevic(1100.0, 4600.0, 2.19), "B": gp.RespuestaDevic(1750.0, 8200.0, 1.58)}       # las de CD.3 y CD.6
DOSIS = (0, 50, 100, 150, 200, 300, 400, 500, 600)
V = dict(zip(("B", "G", "R"), gen.CALIB["virgen_bgr"]))
PISO_DE_LA_PLACA = {"R": V["R"], "G": V["G"], "B": V["B"], "gris": 0.299 * V["R"] + 0.587 * V["G"] + 0.114 * V["B"]}
TODAS = ("R", "G", "B", "gris")
DE_LA_CURVA = ("R", "G", "B")      # CD.5b (01-11, DA-94): las capas de la curva (el gris no tiene curva ni pasa a dosis)
EJE_Y_DOSIS = "dosis [cGy]"
EJE_Y_OD = "densidad óptica neta [1]"
COLUMNAS_DE_SIEMPRE = ("Capa", "Eje", "Estado", "FWHM [mm]", "Desfase izquierdo o superior [mm]", "Desfase derecho o inferior [mm]", "Penumbra izquierda o superior [mm]",
                       "Penumbra derecha o inferior [mm]", "Piso [nivel]", "Meseta [nivel]", "Avisos", "Se guarda")        # las de HEAD, escritas AQUI: la netOD no gana columnas
COLUMNAS_EN_DOSIS = COLUMNAS_DE_SIEMPRE[:10] + ("Dosis de la meseta [cGy]", "U de la dosis de la meseta, k = 2 [cGy]") + COLUMNAS_DE_SIEMPRE[10:]
SIN_CURVA = ("No se puede ver en dosis: no hay curva de dosis: no hay ninguna calibración vigente con una capa válida (se hace con «Curva de dosis...») (la curva de un análisis es la de la calibración "
             "vigente más reciente con al menos una capa «válida» escaneada con la misma cadena de captura que la película).")
REGISTRO = "No se puede ver en dosis: el registro se guardó sin dosis."


class Usuario:
    """El objeto de la sesion (como `ui.Login`): el permiso de «Anular» lee `_nombre` y `_usuario` de el (H-CD5-7)."""
    _nombre = "Fisico de prueba"
    _usuario = "fprueba"


def referencia(medida, valores=None):
    """Una `ReferenciaVirgen` valida cuyo valor por capa es EXACTAMENTE la virgen de la placa (el I0 de las piezas es el mismo), como la de CD.6: la de una virgen MEDIDA (`medida`, con su tabla de
    uniformidad, sus parametros y su region, que una copia guardada exige al reabrir un registro) con las capas de la placa y los 16 bits de su cadena."""
    p = pel()
    valores = PISO_DE_LA_PLACA if valores is None else valores
    capas = {c: p.CapaDelPiso(c, "ok", valores[c], 1000, 1.0, None, None, valores[c]) for c in TODAS}
    return dataclasses.replace(medida, capas=capas, procedencia=dict(medida.procedencia, bits=16, archivo="virgen.tif"))


def calibrar(escala=1.0):
    """La curva (CD.3) de piezas sinteticas de 5 x 5 cm de la MISMA respuesta y el MISMO I0 que la placa, sin ruido, a 600 ppp, 16 bits y en TIFF (la cadena de la placa). `escala` multiplica las dosis
    declaradas (otra curva valida, para probar que cambiar la curva descarta lo calculado)."""
    import importlib
    cd = importlib.import_module("analisisImagenes.curva_dosis")
    P = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
    piezas = []
    for k, d in enumerate(DOSIS):
        datos = gp.pieza_de_dosis(d, (RESP["R"], RESP["G"], RESP["B"]), i0=(V["R"], V["G"], V["B"]), sigma=0.0, bits=16, dpi=600.0, lado_mm=50.0, semilla=k + 1).datos
        medida = pel().medir_pieza_uniforme(datos, P, f"{d}.tif", FECHA, escala="declarada")
        piezas.append(cd.pieza_de_calibracion(k + 1, float(d) * escala, float(d) * escala, medida))
    return cd.ajustar(piezas)


def con_capa(curva, capa, **cambios):
    capas = copy.deepcopy(curva.capas)
    capas[capa].update(cambios)
    return dataclasses.replace(curva, capas=capas)


def calibracion(curva, id_=7, lote="L-31", fecha="2026-10-30"):
    """Lo que da `services.curva_dosis.vigentes_validas()` de una calibracion (lo que lee `curva_efectiva`)."""
    return {"id": id_, "lote": lote, "fecha_irradiacion": fecha, "ajuste": curva.como_dict()}


@pytest.fixture(scope="module")
def escena():
    """La placa de la verdad en dosis (la variante en netOD de CD.6: 16 bits, 600 ppp, sin ruido), su curva valida (rango 600 cGy) y la otra curva (dosis x 1.25), y lo que el MOTOR mide directamente."""
    placa = gen.generar("tiff", bits=16, variante="A", theta_deg=0.4, seed=1, ruido=0.0, respuestas_netod=RESP, dosis_meseta_cgy=DOSIS_MESETA)
    curva = calibrar()
    otra = calibrar(1.25)
    clics = [tuple(float(v) for v in placa.verdad.marcas_px[k]) for k in ("UL", "UR", "DR", "DL", "C")]
    medida = pel().piso_de_pelicula_virgen(_virgen_sintetica(1), copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA), "virgen_lote.tif", fecha_calculo="2026-03-15")
    assert medida.estado == "ok" and medida.uniformidad is not None
    yield types.SimpleNamespace(placa=placa, verdad=placa.verdad, curva=curva, otra=otra, clics=clics, ref=referencia(medida))
    gc.collect()


@pytest.fixture
def mundo(monkeypatch, escena, bd):
    """Lo que la ventana lee de fuera, controlado: la pelicula virgen montada (la de la placa) y las calibraciones vigentes (`mundo.calibraciones`, la lista que devuelve `vigentes_validas`)."""
    estado = types.SimpleNamespace(calibraciones=[calibracion(escena.curva)], lecturas=0)
    monkeypatch.setattr(pel(), "leer_referencia_virgen", lambda carpeta: escena.ref)

    def vigentes():
        estado.lecturas += 1
        return copy.deepcopy(estado.calibraciones)
    import importlib
    monkeypatch.setattr(importlib.import_module("services.curva_dosis"), "vigentes_validas", vigentes)
    return estado


@pytest.fixture
def abierta(fabrica, mundo, escena, dialogos):
    """La ventana con la placa abierta y los cinco puntos marcados (analizada en netOD), con el objeto de la sesion."""
    v = fabrica(usuario=Usuario())
    assert v.cargar_imagen(escena.placa.datos, "placa_dosis.tif")
    for x, y in escena.clics:
        clic(v, x, y)
    assert v.estado == "analizada", v.estado
    return v


def pulsar(v):
    v.boton_dosis.click()


def sin_la_memoria(h):
    """La huella sin los DOS atributos de la memoria del analisis en dosis (`_resultado_en_dosis`, `_barrido_en_dosis`: None antes de pulsar, el analisis despues; quedan a proposito, DA-92)."""
    h = dict(h)
    h["atributos"] = {k: v for k, v in h["atributos"].items() if k not in ("_resultado_en_dosis", "_barrido_en_dosis")}
    return h


def ejes_y(figura):
    return [ax.get_ylabel() for ax in figura.axes if ax.get_ylabel()]


def tabla(t):
    return [tuple(t.horizontalHeaderItem(c).text() for c in range(t.columnCount()))] + [tuple(t.item(r, c).text() for c in range(t.columnCount())) for r in range(t.rowCount())]


def vista_del_registro(w):
    """Todo lo que la ventana MUESTRA de un registro abierto: sus cuatro tablas, sus figuras (rotulos, limites y numero de lineas e imagenes de cada eje), sus lineas de estado y el boton de la dosis."""
    figuras = [[(ax.get_xlabel(), ax.get_ylabel(), ax.get_title(), ax.get_xlim(), ax.get_ylim(), len(ax.lines), len(ax.images)) for ax in fig.axes]
               for fig in (w._fig_capas, w._fig_perfiles, w._fig_barridos, w.eje_cuadratura.figure)]
    tablas = [texto_de_la_tabla(tb) for tb in (w.tabla_desfases, w.tabla_perfiles, w.tabla_barridos, w.tabla_cuadratura)]
    textos = [x.text() for x in (w.linea_dosis, w.linea_regla, w.etiqueta_registro, w.etiqueta_piso, w.nota_pestana1, w.pie_de_parametros)]
    return figuras, tablas, textos, (w.boton_dosis.isEnabled(), w.boton_dosis.isChecked(), w.boton_dosis.toolTip(), w.estado)


# ===================================================================================================== el camino de una persona

class TestElCaminoDeUnaPersona:
    def test_arranca_apagado_y_sin_analisis_no_se_puede_pulsar(self, fabrica, mundo):
        v = fabrica(usuario=Usuario())
        assert v.boton_dosis.text() == "Ver en dosis" and v.boton_dosis.isCheckable() and not v.boton_dosis.isChecked() and not v.boton_dosis.isEnabled()
        assert v.linea_dosis.text() == "" and not v.linea_dosis.isVisibleTo(v), "sin analisis la linea de la dosis no dice nada"
        assert mundo.lecturas == 0, "sin pelicula no se busca ninguna curva"

    def test_con_la_placa_analizada_el_boton_se_habilita_apagado_y_la_linea_dice_la_curva(self, abierta, escena):
        v = abierta
        assert v.boton_dosis.isEnabled() and not v.boton_dosis.isChecked(), "arranca apagado: la ventana muestra la netOD"
        rango = escena.curva.rango("G")
        maxima = escena.curva.capas["G"]["netod_maxima"]
        assert v.linea_dosis.text() == (f"Curva de dosis en uso: lote «L-31», irradiada el 2026-10-30 (calibración 7); rango útil de la capa verde: hasta {rango:g} [cGy] (netOD {maxima:.3f} [1]).")
        assert v._resultado.base == "densidad óptica neta" and v._resultado_en_dosis is None, "no se calcula la dosis hasta que se pulsa"
        assert set(ejes_y(v._fig_perfiles)) == {EJE_Y_OD}

    def test_la_linea_de_la_curva_dice_el_rango_util_de_la_capa_reportada_apagado_y_pulsado(self, abierta, escena):
        """CD7-REV1-R1-P2. Todas las pruebas miraban la linea con la capa verde (la de omision): la ventana podia llamar a `texto_de_la_dosis` con la capa «G» fija y, reportando la azul, seguir diciendo
        «rango util de la capa verde». La linea dice el rango util y la netOD tope de LA capa que se reporta, con el boton apagado y pulsado."""
        v = abierta
        curva = escena.curva
        for capa, adjetivo in (("B", "azul"), ("R", "roja"), ("G", "verde")):
            v.selector_capa.setCurrentIndex(v.selector_capa.findData(capa))
            esperada = (f"Curva de dosis en uso: lote «L-31», irradiada el 2026-10-30 (calibración 7); rango útil de la capa {adjetivo}: hasta {curva.rango(capa):g} [cGy] "
                        f"(netOD {curva.capas[capa]['netod_maxima']:.3f} [1]).")
            assert v.boton_dosis.isEnabled() and v.linea_dosis.text() == esperada, (capa, v.linea_dosis.text())
            pulsar(v)
            assert v.linea_dosis.text() == f"Vista en dosis [cGy]. {esperada}", (capa, v.linea_dosis.text())
            pulsar(v)
        assert curva.capas["B"]["netod_maxima"] != curva.capas["G"]["netod_maxima"], "las capas de la placa de prueba tienen netOD tope distinta: la linea de una no se confunde con la de otra"

    def test_pulsado_muestra_la_dosis_de_la_verdad_en_cada_pestana(self, abierta, escena, dialogos):
        v = abierta
        pulsar(v)
        assert v.boton_dosis.isChecked() and v._resultado_en_dosis is not None and v._resultado_en_dosis.base == "dosis"
        assert not dialogos.de("warning") and not dialogos.de("critical")
        do = v._resultado_en_dosis
        for capa in ("R", "G", "B"):
            m = do.capas[capa]
            assert m.base == "dosis", (capa, m.estado)
            assert abs(m.crossplane.fwhm_mm - 100.0) <= 0.05 and abs(m.inplane.fwhm_mm - 99.0) <= 0.05, (capa, m.crossplane.fwhm_mm, m.inplane.fwhm_mm)
            assert abs(m.dosis_meseta_cgy - DOSIS_MESETA) <= 0.01 * DOSIS_MESETA, (capa, m.dosis_meseta_cgy)
            assert m.crossplane.fwhm_mm < v._resultado.capas[capa].crossplane.fwhm_mm - 0.5, "la netOD sale mas ancha que la dosis (H4)"
        # «Perfiles»: todos en cGy; «Capas»: la barra en cGy (la pestana «Imagen» ya no tiene perfiles: ajuste del 31-10, sin el gris)
        assert set(ejes_y(v._fig_perfiles)) == {EJE_Y_DOSIS}
        barras = [ax.get_xlabel() for ax in v._fig_capas.axes if ax.get_xlabel() and "[px]" not in ax.get_xlabel()]
        assert barras == [EJE_Y_DOSIS] * 3, barras
        # las tablas: los perfiles con la dosis de la meseta y su U; los barridos y los desfases del analisis en dosis
        filas = tabla(v.tabla_perfiles)
        assert filas[0] == COLUMNAS_EN_DOSIS
        verde = [f for f in filas[1:] if f[0] == "Capa verde"]
        assert verde[0][10] == f"{do.capas['G'].dosis_meseta_cgy:.1f}" and verde[0][11] == f"{do.capas['G'].u_dosis_meseta_cgy:.1f}"
        assert texto_de_la_tabla(v.tabla_barridos) == texto_de_la_tabla_de(dibujo_mod().filas_de_los_barridos(v._barrido_en_dosis))
        assert texto_de_la_tabla(v.tabla_barridos) != texto_de_la_tabla_de(dibujo_mod().filas_de_los_barridos(v._barrido)), "el barrido en dosis no es el de netOD"
        lineas = {l.get_gid(): l.get_ydata() for l in v._fig_barridos.axes[0].lines if str(l.get_gid()).startswith("barrido:bandas:G")}         # el primer eje: el crossplane
        esperado = [np.nan if x.fwhm_mm is None else x.fwhm_mm for x in v._barrido_en_dosis.ejes["crossplane"].capas["G"].bandas]
        assert np.allclose(lineas["barrido:bandas:G"], esperado, equal_nan=True), "la grafica de los barridos sigue al boton"
        assert texto_de_la_tabla(v.tabla_desfases) == texto_de_la_tabla_de(dibujo_mod().filas_de_la_capa_reportada(do, "G"))
        assert v.linea_dosis.text().startswith("Vista en dosis [cGy]. Curva de dosis en uso: lote «L-31»")
        assert v.etiqueta_piso.text().startswith("Base de la medida: dosis; cada píxel se convierte en dosis con la curva de su capa")

    def test_apagado_vuelve_a_la_netod_de_antes_identica_y_sin_recalcular(self, abierta, monkeypatch):
        v = abierta
        antes = sin_la_memoria(huella(v))
        pulsar(v)
        calculado = v._resultado_en_dosis
        assert sin_la_memoria(huella(v)) != antes, "pulsado, la vista cambia"
        pulsar(v)
        assert not v.boton_dosis.isChecked() and sin_la_memoria(huella(v)) == antes, "apagado, la vista de netOD es la de antes de pulsar"
        llamadas = []
        monkeypatch.setattr(pm(), "analizar", lambda *a, **k: llamadas.append(1))
        pulsar(v)
        assert v._resultado_en_dosis is calculado and not llamadas, "el analisis en dosis queda en memoria: pulsar otra vez no recalcula"

    def test_la_imagen_con_lo_dibujado_encima_no_cambia_al_pulsar(self, abierta):
        v = abierta

        def imagen():
            capas = []
            for a in v._artistas_de_la_imagen:
                datos = a.get_xydata() if hasattr(a, "get_xydata") else (a.get_path().vertices if hasattr(a, "get_path") else [])
                capas.append((type(a).__name__, str(a.get_gid()), str(a.get_label()), np.round(np.asarray(datos, dtype=float), 6).tolist()))
            return capas, v.eje_imagen.get_xlim(), v.eje_imagen.get_ylim(), len(v.eje_imagen.images)
        antes = imagen()
        pulsar(v)
        assert imagen() == antes, "la imagen con los puntos, el recuadro, las bandas y la region del piso no sigue al boton (DC9)"
        assert v.tabla_cuadratura.rowCount() > 0 and texto_de_la_tabla(v.tabla_cuadratura) == texto_de_la_tabla_de(dibujo_mod().filas_de_la_cuadratura(v._resultado.geometria))

    def test_el_calculo_en_dosis_va_con_el_cursor_de_espera(self, abierta, monkeypatch):
        v = abierta
        cursores = []
        original = pm().analizar

        def espiar(*a, **k):
            cursor = QApplication.overrideCursor()
            cursores.append(None if cursor is None else cursor.shape())
            return original(*a, **k)
        monkeypatch.setattr(pm(), "analizar", espiar)
        pulsar(v)
        assert cursores == [Qt.WaitCursor] and QApplication.overrideCursor() is None

    def test_guardar_guarda_la_netod_aunque_la_vista_este_en_dosis_y_vuelve_a_netod(self, abierta, dialogos, bd):
        v = abierta
        pulsar(v)
        assert v.boton_guardar.isEnabled()
        filas = tabla(v.tabla_perfiles)
        verde = [f for f in filas[1:] if f[0] == "Capa verde"]
        assert verde[0][-1] == "se guarda (en densidad óptica neta y en dosis)"      # CD.6b (31-10, DC16, DA-92): con la vista en dosis la regla se cumple y se guardan las dos
        v.boton_guardar.click()
        assert v.estado == "registro"
        guardado = svc().leer(v.ref)
        assert guardado["capa"] == "G" and guardado["parametros"]["base_de_la_medida"] == "densidad óptica neta"
        assert svc().diferencias(guardado, v._resultado) == [], "lo guardado en netOD son los valores de la vista de netOD"
        # CD.6b (31-10, DC16, DA-92): el registro guardo tambien la dosis con la copia de la curva: el boton queda apagado y puede pasar a dosis con ella
        assert not v.boton_dosis.isChecked() and v.boton_dosis.isEnabled() and guardado["estado_dosis"] == "ok" and guardado["curva"] is not None
        assert set(ejes_y(v._fig_perfiles)) == {EJE_Y_OD}, "un registro se ve en netOD"


def texto_de_la_tabla_de(filas):
    return [list(f) for f in filas]


# ===================================================================================================== la regla del boton

class TestLaRegla:
    def test_sin_curva_queda_gris_y_dice_el_motivo_con_la_regla_entera(self, fabrica, mundo, escena, dialogos):
        mundo.calibraciones = []
        v = fabrica(usuario=Usuario())
        v.cargar_imagen(escena.placa.datos, "p.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        assert not v.boton_dosis.isEnabled() and v.linea_dosis.text() == SIN_CURVA
        ayuda = v.boton_dosis.toolTip()
        assert pm().CONDICIONES_PARA_PASAR_A_DOSIS in ayuda and "Ahora no se puede: no hay curva de dosis" in ayuda, "la ayuda dice la regla ENTERA y el motivo (CD5-PROD-R1-01)"
        assert v.linea_dosis.toolTip() == pm().CONDICIONES_PARA_PASAR_A_DOSIS
        v._al_ver_en_dosis(True)
        assert not v.boton_dosis.isChecked() and v._resultado_en_dosis is None, "un boton deshabilitado no pasa a dosis aunque lo llamen"

    def test_con_una_curva_guia_queda_gris(self, fabrica, mundo, escena):
        guia = dataclasses.replace(escena.curva, cero=dict(escena.curva.cero, fuente="pieza_de_menor_dosis", detalle="la pieza de 50 cGy"))
        mundo.calibraciones = [calibracion(guia)]
        v = fabrica(usuario=Usuario())
        v.cargar_imagen(escena.placa.datos, "p.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        assert not v.boton_dosis.isEnabled()
        assert v.linea_dosis.text() == ("No se puede ver en dosis: la curva de la capa verde es una guía: su cero no es una pieza de 0 cGy ni la película virgen montada (la pieza de 50 cGy).")

    def test_con_otra_cadena_queda_gris(self, fabrica, mundo, escena):
        otra = dataclasses.replace(escena.curva, cadena=dict(escena.curva.cadena, bits=8))
        mundo.calibraciones = [calibracion(otra)]
        v = fabrica(usuario=Usuario())
        v.cargar_imagen(escena.placa.datos, "p.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        assert not v.boton_dosis.isEnabled() and v.linea_dosis.text().startswith("No se puede ver en dosis: no hay curva de dosis para la cadena de captura de esta película")

    def test_con_el_piso_de_las_esquinas_queda_gris_y_vuelve_con_la_virgen(self, abierta):
        v = abierta
        v.selector_piso.setCurrentIndex(v.selector_piso.findData("automatico"))
        assert v.estado == "analizada" and not v.boton_dosis.isEnabled()
        assert v.linea_dosis.text() == "No se puede ver en dosis: el piso no es el de la película virgen (el de las esquinas de la película): la dosis lo exige."
        v.selector_piso.setCurrentIndex(v.selector_piso.findData("virgen"))
        assert v.boton_dosis.isEnabled()

    def test_la_regla_es_la_de_la_capa_reportada(self, fabrica, mundo, escena):
        mundo.calibraciones = [calibracion(con_capa(escena.curva, "R", estado="no válida: de prueba"))]
        v = fabrica(usuario=Usuario())
        v.cargar_imagen(escena.placa.datos, "p.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        assert v.capa_reportada == "G" and v.boton_dosis.isEnabled()
        v.selector_capa.setCurrentIndex(v.selector_capa.findData("R"))
        assert not v.boton_dosis.isEnabled() and v.linea_dosis.text() == "No se puede ver en dosis: la curva de la capa roja no es válida: no válida: de prueba."

    def test_cambiar_a_una_capa_que_no_cumple_vuelve_la_vista_a_netod(self, fabrica, mundo, escena):
        mundo.calibraciones = [calibracion(con_capa(escena.curva, "R", estado="no válida: de prueba"))]
        v = fabrica(usuario=Usuario())
        v.cargar_imagen(escena.placa.datos, "p.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        pulsar(v)
        assert set(ejes_y(v._fig_perfiles)) == {EJE_Y_DOSIS}
        v.selector_capa.setCurrentIndex(v.selector_capa.findData("R"))
        assert not v.boton_dosis.isChecked() and not v.boton_dosis.isEnabled()
        assert set(ejes_y(v._fig_perfiles)) == {EJE_Y_OD}, "la vista vuelve a netOD"
        assert "la curva de la capa roja no es válida" in v.linea_dosis.text()
        v.selector_capa.setCurrentIndex(v.selector_capa.findData("B"))
        assert v.boton_dosis.isEnabled() and not v.boton_dosis.isChecked()

    def test_una_capa_que_no_se_mide_en_dosis_lo_dice_sin_numeros(self, fabrica, mundo, escena):
        mundo.calibraciones = [calibracion(con_capa(escena.curva, "B", estado="no válida: de prueba"))]
        v = fabrica(usuario=Usuario())
        v.cargar_imagen(escena.placa.datos, "p.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        pulsar(v)
        azul = [f for f in tabla(v.tabla_perfiles)[1:] if f[0] == "Capa azul"]
        assert all(f[2] == "no medible en dosis: la curva de la capa azul no es válida: no válida: de prueba" and f[3] == "no medible" and f[10] == "no medible" and f[11] == "no medible"
                   for f in azul), azul
        verde = [f for f in tabla(v.tabla_perfiles)[1:] if f[0] == "Capa verde"]
        assert verde[0][10] != "no medible", "la dosis de la meseta de cada fila es la de SU capa"


# ===================================================================================================== la memoria: lo que descarta el analisis en dosis

class TestLoQueDescartaLaDosis:
    def test_cambiar_los_puntos_descarta_la_dosis(self, abierta, escena):
        v = abierta
        pulsar(v)
        viejo = v._resultado_en_dosis
        v.boton_recalcular.click()
        assert v._resultado_en_dosis is None and not v.boton_dosis.isChecked() and not v.boton_dosis.isEnabled()
        for x, y in escena.clics:
            clic(v, x + 3.0, y - 2.0)
        assert v.estado == "analizada" and not v.boton_dosis.isChecked()
        pulsar(v)
        assert v._resultado_en_dosis is not viejo
        assert [m["clic"] for m in v._resultado_en_dosis.como_dict()["marcas"]] == [m["clic"] for m in v._resultado.como_dict()["marcas"]], "la dosis es de los puntos NUEVOS"

    def test_cambiar_el_piso_descarta_la_dosis(self, abierta):
        v = abierta
        pulsar(v)
        v.selector_piso.setCurrentIndex(v.selector_piso.findData("automatico"))
        assert v._resultado_en_dosis is None and not v.boton_dosis.isChecked()

    def test_otra_pelicula_descarta_la_dosis(self, abierta, escena):
        v = abierta
        pulsar(v)
        assert v.cargar_imagen(escena.placa.datos, "otra.tif")
        assert v._resultado_en_dosis is None and not v.boton_dosis.isChecked() and not v.boton_dosis.isEnabled()

    def test_otra_curva_descarta_la_dosis_al_volver_de_la_calibracion(self, abierta, mundo, escena):
        v = abierta
        pulsar(v)
        assert v._resultado_en_dosis.curva.como_dict() == escena.curva.como_dict()
        mundo.calibraciones = [calibracion(escena.otra, id_=8, lote="L-32")] + mundo.calibraciones
        ventana = v._al_abrir_la_curva()
        assert v._resultado_en_dosis is not None, "abrir la calibracion no cambia nada"
        ventana.close()
        assert v._resultado_en_dosis is None and not v.boton_dosis.isChecked(), "al cerrar la calibracion la curva cambio: la dosis se descarta y la vista vuelve a netOD"
        assert set(ejes_y(v._fig_perfiles)) == {EJE_Y_OD}
        assert "lote «L-32»" in v.linea_dosis.text() and v.boton_dosis.isEnabled()
        pulsar(v)
        assert v._resultado_en_dosis.curva.como_dict() == escena.otra.como_dict(), "la dosis nueva es de la curva nueva"

    def test_otra_curva_con_la_vista_apagada_tambien_descarta_la_dosis_en_memoria(self, abierta, mundo, escena):
        """CD7-REV1-R1-P1. El plan pide que la memoria se descarte si cambia la curva, sin condicionarlo al boton: con «Ver en dosis» APAGADO la dosis calculada con la curva vieja seguia en memoria y, al volver
        a pulsar, se mostraba la dosis de la vieja mientras la linea ya nombraba la nueva."""
        v = abierta
        pulsar(v)
        viejo = v._resultado_en_dosis
        assert viejo.curva.como_dict() == escena.curva.como_dict()
        pulsar(v)
        assert not v.boton_dosis.isChecked() and v._resultado_en_dosis is viejo, "apagado, la dosis queda en memoria (a proposito) mientras la curva sea la misma"
        mundo.calibraciones = [calibracion(escena.otra, id_=8, lote="L-32")] + mundo.calibraciones
        v._al_abrir_la_curva().close()
        assert v._resultado_en_dosis is None and v._barrido_en_dosis is None, "la curva cambio: la dosis calculada con la vieja se descarta aunque la vista este en netOD"
        assert "lote «L-32»" in v.linea_dosis.text() and v.boton_dosis.isEnabled() and not v.boton_dosis.isChecked()
        pulsar(v)
        assert v._resultado_en_dosis is not viejo and v._resultado_en_dosis.curva.como_dict() == escena.otra.como_dict(), "pulsar otra vez muestra la dosis de la curva NUEVA, la que dice la linea"

    def test_la_misma_curva_no_descarta_la_dosis(self, abierta):
        v = abierta
        pulsar(v)
        calculado = v._resultado_en_dosis
        v.refrescar()
        assert v._resultado_en_dosis is calculado and v.boton_dosis.isChecked()

    def test_la_curva_anulada_al_volver_deja_el_boton_gris(self, abierta, mundo):
        v = abierta
        pulsar(v)
        mundo.calibraciones = []
        v._al_abrir_la_curva().hide()
        assert not v.boton_dosis.isEnabled() and not v.boton_dosis.isChecked() and v.linea_dosis.text() == SIN_CURVA


# ===================================================================================================== lo que lo deja apagado

class TestLoQueLoDejaApagado:
    def test_limpiar_lo_deja_apagado_como_una_ventana_nueva(self, abierta, fabrica):
        v = abierta
        pulsar(v)
        v.boton_limpiar.click()
        assert not v.boton_dosis.isChecked() and not v.boton_dosis.isEnabled() and v.linea_dosis.text() == ""
        nueva = fabrica(ref=v.ref, usuario=Usuario())
        assert huella(v)["widgets"] == huella(nueva)["widgets"]

    def test_abrir_un_registro_lo_deja_gris_aunque_haya_una_curva_vigente_valida(self, abierta, fabrica, mundo):
        v = abierta
        vigentes, mundo.calibraciones = mundo.calibraciones, []      # CD.6b (31-10, DC16, DA-92): un registro guardado SIN dosis (no habia curva al guardar); el que la tiene lo prueba test_cd6b
        v.refrescar()
        v.boton_guardar.click()
        mundo.calibraciones = vigentes
        assert v.estado == "registro"
        lecturas = mundo.lecturas
        otra = fabrica(ref=v.ref, usuario=Usuario())
        assert otra.estado == "registro" and not otra.boton_dosis.isChecked() and not otra.boton_dosis.isEnabled()
        assert otra.linea_dosis.text() == REGISTRO and "el registro se guardó sin dosis" in otra.boton_dosis.toolTip()
        assert mundo.lecturas == lecturas, "un registro nunca busca la curva vigente (DA-81: la copia guardada manda; CD.6b)"
        puntos = [tuple(m["clic"]) for m in otra._registro["puntos"]]
        otra.boton_recalcular.click()
        for x, y in puntos:
            clic(otra, x, y)
        assert otra.estado == "analizada" and otra.boton_dosis.isEnabled(), "tras «Recalcular» es un analisis nuevo: la imagen del registro tiene su cadena y su curva"


# ===================================================================================================== «Curva de dosis...»

class TestLaVentanaDeCalibracion:
    def test_abre_la_de_cd5_con_el_objeto_de_la_sesion_una_sola_vez(self, abierta):
        v = abierta
        assert v.boton_curva.text() == "Curva de dosis..."
        v.boton_curva.click()
        ventana = v._ventana_curva
        assert type(ventana).__name__ == "VentanaCurvaDosis" and ventana.isVisible() and ventana.parent() is v
        assert ventana._usuario_de_la_sesion is v._usuario_de_la_sesion and isinstance(ventana._usuario_de_la_sesion, Usuario), "el permiso de «Anular» necesita el OBJETO (H-CD5-7)"
        assert ventana.usuario == "Fisico de prueba" == v.usuario
        v.boton_curva.click()
        assert v._ventana_curva is ventana, "una sola por ventana mensual"
        cerrar(ventana)

    def test_anular_la_curva_vigente_al_cerrar_la_calibracion_no_cambia_un_registro_abierto(self, abierta, fabrica, mundo):
        """CD7-REV1-R1-P5. El protocolo de CD.7: «anular la curva vigente (al cerrar la calibracion) deja el boton gris en un analisis de la sesion y no cambia un registro». Las otras pruebas que abren la
        calibracion lo hacen con un analisis de la sesion, nunca con un registro a la vista: con el la ventana ni busca la curva vigente (DA-81: la copia guardada manda; CD.6b) ni cambia nada de lo que muestra."""
        v = abierta
        vigentes, mundo.calibraciones = mundo.calibraciones, []      # CD.6b (31-10, DC16, DA-92): un registro guardado SIN dosis (no habia curva al guardar); el que la tiene lo prueba test_cd6b
        v.refrescar()
        v.boton_guardar.click()
        mundo.calibraciones = vigentes
        otra = fabrica(ref=v.ref, usuario=Usuario())
        assert otra.estado == "registro" and otra.linea_dosis.text() == REGISTRO
        antes, lecturas = vista_del_registro(otra), mundo.lecturas
        mundo.calibraciones = []                          # la curva vigente se anulo (en la calibracion)
        otra._al_abrir_la_curva().close()
        assert mundo.lecturas == lecturas, "con un registro a la vista no se busca la curva vigente, ni al abrir la calibracion ni al cerrarla"
        assert vista_del_registro(otra) == antes, "el registro se ve exactamente igual: tablas, figuras, lineas y boton"
        assert not otra.boton_dosis.isEnabled() and otra.linea_dosis.text() == REGISTRO and otra.estado == "registro"

    def test_la_pagina_le_pasa_el_objeto_de_la_sesion(self):
        """`imagen_del_campo.abrir_analisis_placa` construye la ventana con `pagina.user_id` (el objeto; su `_nombre` es el que auditaba `usuario_actual`) y, sin el, con el nombre."""
        fuente = (RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "imagen_del_campo.py").read_text(encoding="utf-8")
        llamadas = [n for n in ast.walk(ast.parse(fuente)) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "VentanaPlacaMensual"]
        assert len(llamadas) == 1
        assert ast.unparse(llamadas[0].args[2]) == "getattr(pagina, 'user_id', None) or usuario_actual(pagina)"

    def test_con_el_nombre_la_ventana_audita_igual(self, fabrica, mundo):
        v = fabrica(usuario="Fisico de prueba")
        assert v.usuario == "Fisico de prueba" == v._usuario_de_la_sesion


# ===================================================================================================== el dibujo (sin Qt)

@pytest.fixture(scope="module")
def medidos(escena):
    """El analisis en netOD y en dosis de la placa, del MOTOR directamente (el oraculo del dibujo)."""
    P = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
    pelicula = pel().leer_pelicula(escena.placa.datos)
    cadena = pm().cadena_de_la_pelicula(escena.placa.datos, pelicula)
    od = pm().analizar(pelicula, escena.clics, P, modo_piso="virgen", referencia_virgen=escena.ref)
    P["base_de_la_medida"] = "dosis"
    do = pm().analizar(pelicula, escena.clics, P, modo_piso="virgen", referencia_virgen=escena.ref, curva=escena.curva, cadena=cadena)
    sin_azul = pm().analizar(pelicula, escena.clics, P, modo_piso="virgen", referencia_virgen=escena.ref, curva=con_capa(escena.curva, "B", estado="no válida: de prueba"), cadena=cadena)
    yield types.SimpleNamespace(od=od, do=do, sin_azul=sin_azul)
    gc.collect()


class TestElDibujoEnDosis:
    def test_el_eje_de_la_dosis_sale_solo_de_la_curva(self, escena):
        d = dibujo_mod()
        rangos = [escena.curva.rango(c) for c in DE_LA_CURVA if escena.curva.estado(c) == "válida"]
        assert d.eje_de_la_dosis(escena.curva) == 50.0 * math.ceil(max(rangos) / 50.0) and d.PASO_DEL_EJE_DE_LA_DOSIS_CGY == 50.0
        mas = con_capa(escena.curva, "G", rango_cgy=612.0)
        assert d.eje_de_la_dosis(mas) == 650.0, "redondeado hacia ARRIBA a 50 cGy"
        nada = escena.curva
        for c in DE_LA_CURVA:
            nada = con_capa(nada, c, estado="no válida: de prueba")
        assert d.eje_de_la_dosis(nada) is None

    def test_la_capa_valida_de_mayor_rango_manda_en_el_eje_fijo_y_una_no_valida_no(self, escena):
        """CD7-REV1-R1-P3. CD7-D7: el eje fijo va hasta la mayor dosis util de las capas validas de la curva. Las capas de la curva sintetica tienen el mismo rango (600 cGy), asi que la prueba
        anterior no distinguia una capa de otra. CD.5b (01-11, DA-94): era «el gris entra en el eje» (P27 de la curva); el gris ya no tiene curva y no cuenta (lo fija test_cd5b), y la prueba se queda con
        su intencion sobre la azul."""
        d = dibujo_mod()
        assert d.eje_de_la_dosis(escena.curva) == 600.0
        con_gris = con_capa(escena.curva, "B", rango_cgy=712.0)
        assert d.eje_de_la_dosis(con_gris) == 750.0, "la azul tiene el mayor rango util de la curva: el eje llega hasta ella, redondeado hacia arriba a 50 cGy"
        gris_no_valido = con_capa(con_gris, "B", estado="no válida: de prueba")
        assert d.eje_de_la_dosis(gris_no_valido) == 600.0, "una capa que no es valida no cuenta para el eje"
        assert d.eje_de_la_dosis(con_capa(escena.curva, "R", rango_cgy=712.0)) == 750.0

    def test_cada_perfil_en_dosis_tiene_el_mismo_eje_fijo_y_el_rotulo_en_cgy(self, medidos, escena):
        from matplotlib.figure import Figure
        d = dibujo_mod()
        tope = d.eje_de_la_dosis(escena.curva)
        limites = set()
        for capa in DE_LA_CURVA:      # CD.5b (01-11, DA-94): el gris en dosis es «no medible en dosis» (no tiene curva)
            for eje in ("crossplane", "inplane"):
                ax = Figure().add_subplot(111)
                d.dibujar_perfil(ax, getattr(medidos.do.capas[capa], eje), capa, medidos.do.parametros, curva=medidos.do.curva)
                assert ax.get_ylabel() == EJE_Y_DOSIS
                limites.add(ax.get_ylim())
        assert limites == {(0.0, tope)}, "el eje de la regla (DC9), el mismo en todos: no el de cada perfil"
        ax = Figure().add_subplot(111)
        d.dibujar_perfil(ax, medidos.od.capas["G"].crossplane, "G", medidos.od.parametros)
        assert ax.get_ylabel() == EJE_Y_OD and ax.get_ylim() != (0.0, tope), "en netOD el eje es el de siempre"

    def test_un_perfil_en_dosis_sin_curva_es_un_error(self, medidos):
        from matplotlib.figure import Figure
        with pytest.raises(ValueError, match="con la curva del análisis"):
            dibujo_mod().dibujar_perfil(Figure().add_subplot(111), medidos.do.capas["G"].crossplane, "G", medidos.do.parametros)

    def test_el_perfil_se_dibuja_con_la_curva_de_su_capa(self, medidos):
        from matplotlib.figure import Figure
        d = dibujo_mod()
        m = medidos.do.capas["R"].crossplane
        ax = Figure().add_subplot(111)
        d.dibujar_perfil(ax, m, "R", medidos.do.parametros, curva=medidos.do.curva)
        crudo = [l for l in ax.lines if l.get_gid() == "perfil:crudo"][0].get_ydata()
        esperado = pm().valores_en_la_base("dosis", m.perfil.valores, m.piso, pm().curva_de_la_capa(medidos.do.curva, "R"))
        assert np.allclose(crudo, esperado, rtol=0, atol=1e-9, equal_nan=True)
        meseta = [l for l in ax.lines if l.get_gid() == "perfil:meseta"][0].get_ydata()[0]
        assert abs(meseta - DOSIS_MESETA) <= 0.01 * DOSIS_MESETA

    def test_la_pestana_capas_en_dosis_tiene_la_escala_del_eje(self, medidos, escena):
        d = dibujo_mod()
        tope = d.eje_de_la_dosis(escena.curva)
        for capa in ("R", "G", "B"):
            c = d.capa_acondicionada(medidos.do, capa)
            assert c.tope == tope and c.unidad == EJE_Y_DOSIS and c.texto.startswith(f"de 0 a {tope:g} [cGy], el eje de la dosis de la curva; dosis de la meseta ")
            assert abs(np.nanmedian(c.valores[c.valores > 0.9 * DOSIS_MESETA]) - DOSIS_MESETA) <= 0.01 * DOSIS_MESETA
        assert d.escala_de_las_capas(medidos.do, {c: d.capa_acondicionada(medidos.do, c) for c in ("R", "G", "B")}) is None, "en dosis la escala comun es el eje de la curva"

    def test_una_capa_no_medible_en_dosis_no_se_pinta_en_otra_base(self, medidos):
        c = dibujo_mod().capa_acondicionada(medidos.sin_azul, "B")
        assert np.isnan(c.valores).all() and c.texto == medidos.sin_azul.capas["B"].estado and c.texto.startswith("no medible en dosis: ")

    def test_la_tabla_gana_sus_columnas_solo_en_dosis(self, medidos):
        d = dibujo_mod()
        assert d.columnas_de_los_perfiles("densidad óptica neta") == COLUMNAS_DE_SIEMPRE == d.COLUMNAS_DE_LOS_PERFILES
        assert d.columnas_de_los_perfiles("dosis") == COLUMNAS_EN_DOSIS
        od = d.filas_de_los_perfiles(medidos.od, "G", None)
        assert all(len(f) == len(COLUMNAS_DE_SIEMPRE) for f in od) and [f for f in od if f[0] == "Capa verde"][0][-1] == "se guarda"
        do = d.filas_de_los_perfiles(medidos.do, "G", None)
        assert all(len(f) == len(COLUMNAS_EN_DOSIS) for f in do)
        for f in do:
            capa = {"Capa roja": "R", "Capa verde": "G", "Capa azul": "B", "Gris": "gris"}[f[0]]
            assert f[10] == d.numero(medidos.do.capas[capa].dosis_meseta_cgy, 1) and f[11] == d.numero(medidos.do.capas[capa].u_dosis_meseta_cgy, 1)
        azul = [f for f in d.filas_de_los_perfiles(medidos.sin_azul, "G", None) if f[0] == "Capa azul"]
        assert all(f[10] == "no medible" for f in azul)

    def test_la_linea_de_la_dosis(self, escena):
        d = dibujo_mod()
        efectiva = pm().CurvaEfectiva(escena.curva, 7, "L-31", "2026-10-30")
        assert d.texto_de_la_dosis(None, "G", False, None) == ""
        assert d.texto_de_la_dosis(None, "G", False, "no hay curva de dosis") == "No se puede ver en dosis: no hay curva de dosis."
        base = d.texto_de_la_dosis(efectiva, "G", True, None)
        assert base.startswith("Curva de dosis en uso: lote «L-31», irradiada el 2026-10-30 (calibración 7); rango útil de la capa verde: hasta ")
        assert d.texto_de_la_dosis(efectiva, "G", True, None, True, ("Aviso uno.",)) == f"Vista en dosis [cGy]. {base} Aviso uno."

    def test_la_base_dosis_tiene_su_frase(self):
        assert dibujo_mod().texto_de_la_base("dosis").startswith("Base de la medida: dosis; cada píxel se convierte en dosis con la curva de su capa, n = D(netOD(valor)) / D(netOD(meseta))")


# ===================================================================================================== el parametro 42 (H-CD6-6: la deuda que cierra CD.7)

class TestElParametro42:
    def test_tiene_su_frase_en_el_pie_solo_en_dosis_con_el_valor_con_que_se_midio(self):
        d = dibujo_mod()
        assert d.TRAZO_DE_PARAMETRO["diferencia_virgen_maxima_pct"] == ("dosis", "en dosis, aviso si la película virgen difiere más de {:g} % del cero de la curva")
        assert set(d.TRAZO_DE_PARAMETRO) == set(pm().VALORES_DE_LA_GEOMETRIA) and len(d.TRAZO_DE_PARAMETRO) == 43      # segunda pasada (01-11): el 43 es `nivel_de_llegada_al_piso`
        P = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
        P["diferencia_virgen_maxima_pct"] = 3.5
        assert "en dosis, aviso si la película virgen" not in d.texto_de_parametros(P), "en netOD (lo guardado, lo que imprime el PDF de F.1) el pie es el de siempre"
        P["base_de_la_medida"] = "dosis"
        assert "en dosis, aviso si la película virgen difiere más de 3.5 % del cero de la curva" in d.texto_de_parametros(P)

    def test_el_pie_de_la_ventana_en_dosis_lo_dice(self, abierta):
        v = abierta
        assert "en dosis, aviso si la película virgen" not in v.pie_de_parametros.text()
        pulsar(v)
        assert "en dosis, aviso si la película virgen difiere más de 2 % del cero de la curva" in v.pie_de_parametros.text()

    def test_un_registro_sin_el_42_dice_el_pie_de_siempre(self):
        d = dibujo_mod()
        P = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
        del P["diferencia_virgen_maxima_pct"]
        Q = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
        assert d.texto_de_parametros(P) == d.texto_de_parametros(Q), "un registro de antes de CD.6 (41 parametros) y uno nuevo (42) imprimen el MISMO pie en netOD"


# ===================================================================================================== las defensas (lo que la cobertura de lineas mostro sin prueba)

class TestLasDefensas:
    def test_sin_la_cadena_de_la_pelicula_lo_dice(self, fabrica, mundo, escena, monkeypatch):
        def falla(*a, **k):
            raise ValueError("de prueba")
        monkeypatch.setattr(pm(), "cadena_de_la_pelicula", falla)
        v = fabrica(usuario=Usuario())
        v.cargar_imagen(escena.placa.datos, "p.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        assert v._cadena is None and not v.boton_dosis.isEnabled() and mundo.lecturas == 0
        assert v.linea_dosis.text().startswith("No se puede ver en dosis: no hay curva de dosis: no se conoce la cadena de captura de la película (la curva de un análisis es")

    def test_si_no_se_pueden_leer_las_calibraciones_lo_dice(self, fabrica, mundo, escena, monkeypatch):
        import importlib
        import sqlite3

        def falla():
            raise sqlite3.OperationalError("database is locked")
        monkeypatch.setattr(importlib.import_module("services.curva_dosis"), "vigentes_validas", falla)
        v = fabrica(usuario=Usuario())
        v.cargar_imagen(escena.placa.datos, "p.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        assert not v.boton_dosis.isEnabled() and v.linea_dosis.text() == "No se puede ver en dosis: no hay curva de dosis: no se pudieron leer las calibraciones (OperationalError: database is locked)."

    def test_un_analisis_en_otra_base_no_pasa_a_dosis(self, fabrica, mundo, escena, monkeypatch):
        monkeypatch.setitem(pm().VALORES_DE_LA_GEOMETRIA, "base_de_la_medida", pm().BASE_VALOR_DE_PIXEL)
        v = fabrica(usuario=Usuario())
        v.cargar_imagen(escena.placa.datos, "p.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        assert not v.boton_dosis.isEnabled() and v.linea_dosis.text() == "No se puede ver en dosis: el análisis no está en densidad óptica neta (valor de píxel normalizado)."

    def test_si_el_analisis_en_dosis_falla_avisa_y_queda_en_netod(self, abierta, monkeypatch, dialogos):
        v = abierta
        original = pm().analizar

        def falla(pelicula, puntos, P, **k):
            if P.get("base_de_la_medida") == "dosis":
                raise ValueError("de prueba")
            return original(pelicula, puntos, P, **k)
        monkeypatch.setattr(pm(), "analizar", falla)
        pulsar(v)
        assert not v.boton_dosis.isChecked() and v._resultado_en_dosis is None and v.boton_dosis.isEnabled()
        assert [c["texto"] for c in dialogos.de("warning")] == ["No se pudo pasar a dosis: de prueba."]
        assert QApplication.overrideCursor() is None and set(ejes_y(v._fig_perfiles)) == {EJE_Y_OD}

    @pytest.mark.parametrize("error", [RuntimeError("fallo de prueba"), MemoryError("sin memoria de prueba")], ids=["RuntimeError", "MemoryError"])
    def test_un_fallo_inesperado_al_pasar_a_dosis_tambien_deja_el_boton_apagado_y_la_vista_en_netod(self, abierta, monkeypatch, dialogos, error):
        """CD7-REV1-PROD-02. Lo que NO es un `ValueError` (un `RuntimeError`, un `MemoryError` con una pagina entera) dejaba el boton PULSADO con toda la vista en netOD y la linea de la dosis sin decirlo:
        subia a `_protegido`, que avisaba pero no restablecia nada. Igual que `_calcular`, cualquier fallo del analisis en dosis avisa con un cuadro de error y deja lo mismo que un `ValueError`."""
        v = abierta
        original = pm().analizar

        def falla(pelicula, puntos, P, **k):
            if P.get("base_de_la_medida") == "dosis":
                raise error
            return original(pelicula, puntos, P, **k)
        monkeypatch.setattr(pm(), "analizar", falla)
        dialogos.criticos_esperados = True               # el aviso de un fallo inesperado es un `critical`
        pulsar(v)
        assert not v.boton_dosis.isChecked() and v._resultado_en_dosis is None and v._barrido_en_dosis is None and v.boton_dosis.isEnabled(), "el boton no se queda pulsado con la vista en netOD"
        assert [c["texto"] for c in dialogos.de("critical")] == [f"Error inesperado al pasar a dosis ({type(error).__name__}: {error})."] and not dialogos.de("warning")
        assert QApplication.overrideCursor() is None and set(ejes_y(v._fig_perfiles)) == {EJE_Y_OD}
        assert not v.linea_dosis.text().startswith("Vista en dosis") and v.linea_dosis.text().startswith("Curva de dosis en uso"), "la linea sigue diciendo la curva en uso, no que se ve en dosis"
        monkeypatch.setattr(pm(), "analizar", original)
        pulsar(v)
        assert v.boton_dosis.isChecked() and v._resultado_en_dosis is not None, "tras el fallo, pulsar otra vez calcula en dosis como siempre"

    def test_cambiar_la_capa_sin_analisis_no_hace_nada(self, fabrica, mundo):
        v = fabrica(usuario=Usuario())
        v.selector_capa.setCurrentIndex(v.selector_capa.findData("B"))
        assert not v.boton_dosis.isEnabled() and v.linea_dosis.text() == ""

    def test_la_pagina_abre_la_ventana_con_el_objeto_de_la_sesion(self, mundo, bd, dialogos):
        """El camino REAL de quien abre la ventana (E.2): `abrir_analisis_placa(pagina)` con la pagina del control y su `user_id`."""
        import importlib
        from PyQt5.QtWidgets import QWidget
        from test_d1_guardado_placa_mensual import _control
        campo = importlib.import_module("ui.paginasControles.PruebasMensuales.imagen_del_campo")
        pagina = QWidget()
        pagina.ref, pagina.equipo_f, pagina.user_id = _control(bd), "Clinac de prueba", Usuario()
        v = campo.abrir_analisis_placa(pagina)
        try:
            assert v is not None and v._usuario_de_la_sesion is pagina.user_id and v.usuario == "Fisico de prueba"
        finally:
            cerrar(v)
            cerrar(pagina)


# ===================================================================================================== la estructura

class TestEstructura:
    def test_la_ventana_no_escribe_sql_y_lee_las_calibraciones_por_el_servicio(self):
        fuente = (RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "placa_mensual.py").read_text(encoding="utf-8")
        assert "execute(" not in fuente and "SELECT" not in fuente and "import sqlite3" not in fuente
        assert "densidad óptica neta" not in fuente, "el nombre de una base lo dice el motor (OD.1)"
        assert "svc_curva.vigentes_validas()" in fuente and fuente.count("motor.curva_efectiva(") == 2 and fuente.count("motor.se_puede_pasar_a_dosis(") == 1, "UNA regla del boton, la del motor"
        arbol = ast.parse(fuente)
        modulo = {n.module for n in arbol.body if isinstance(n, ast.ImportFrom)}
        assert "ui.paginasControles.PruebasMensuales.curva_dosis" not in modulo, "la ventana de CD.5 se importa DIFERIDA: ella importa piezas de esta (un import circular)"

    def test_el_dibujo_no_importa_qt_ni_pyplot(self):
        arbol = ast.parse((RAIZ / "analisisImagenes" / "dibujo_placa_mensual.py").read_text(encoding="utf-8"))
        importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
        assert not {m for m in importados if m and (m.startswith("PyQt5") or m.endswith("pyplot"))}, importados

    def test_build_exe_lista_la_ventana_y_su_dibujo(self):
        crudo = (RAIZ / "build_exe.py").read_bytes()
        assert b"\r\n" in crudo and b"\n" not in crudo.replace(b"\r\n", b""), "build_exe.py sigue en CRLF"
        texto = crudo.decode("utf-8")
        for modulo in ("ui.paginasControles.PruebasMensuales.placa_mensual", "analisisImagenes.dibujo_placa_mensual", "ui.paginasControles.PruebasMensuales.curva_dosis"):
            assert f'"{modulo}",' in texto

    def test_los_textos_nuevos_sin_simbolos_y_con_unidades_entre_corchetes(self, abierta):
        v = abierta
        pulsar(v)
        textos = [v.boton_dosis.text(), v.boton_dosis.toolTip(), v.boton_curva.text(), v.boton_curva.toolTip(), v.linea_dosis.text(), v.linea_dosis.toolTip(), *todos_los_textos(v)]
        assert all(sin_simbolos(t) for t in textos)
        assert "[cGy]" in v.linea_dosis.text() and " cGy" not in v.linea_dosis.text().replace("cGy).", "").split("Vista en dosis")[1].split("Curva de dosis en uso")[1], "las unidades de la linea, entre corchetes"


# ===================================================================================================== el ajuste del 31-10 (pedidos del fisico)

ALTO_Y_ANCHO = (1297, 706)          # la ventana en la pantalla de 1366 x 768 del fisico (lo que mide `scripts/cd7_ajuste_medir_ventana.py`)


def _fila_de(v, boton):
    """El QHBoxLayout de la barra que lleva `boton`, y el indice del boton en el."""
    from PyQt5.QtWidgets import QHBoxLayout
    for capa in v.findChildren(QHBoxLayout):
        if capa.indexOf(boton) >= 0:
            return capa, capa.indexOf(boton)
    raise AssertionError("el boton no esta en ninguna fila")


def _alto(v):
    """Lo que se ve de la imagen (el area de su lienzo) y de las pestanas, con los eventos procesados."""
    QApplication.processEvents()
    return (v.lienzo_imagen.parentWidget().height(), v.lienzo_imagen.parentWidget().width(), v.pestanas.height(), v.tabla_desfases.height())


class TestElCuadroInfo:
    def test_las_explicaciones_no_estan_en_la_ventana_sino_en_el_cuadro_info(self, abierta):
        v = abierta
        modulo = ventana_mod()
        assert modulo.EXPLICACIONES_EN_LA_INFO == ("etiqueta_marcas", "etiqueta_piso", "linea_dosis", "nota_pestana1", "pie_de_parametros")
        for nombre in modulo.EXPLICACIONES_EN_LA_INFO:
            w = getattr(v, nombre)
            assert w.window() is v.dialogo_info, f"{nombre} vive en el cuadro «Info», no en la ventana"
            assert not w.isVisibleTo(v), f"{nombre} no se ve en la ventana con el cuadro cerrado"
        assert v.etiqueta_marcas.text().startswith("Marcas 5 de 5."), "el contador de las marcas se sigue escribiendo (lo dice el cuadro)"
        assert not hasattr(modulo, "ALTO_DEL_PIE")

    def test_el_boton_info_esta_a_la_derecha_de_guardar_y_es_el_ultimo(self, fabrica, mundo):
        v = fabrica(usuario=Usuario())
        capa, i = _fila_de(v, v.boton_guardar)
        assert capa.indexOf(v.boton_info) == i + 1 == capa.count() - 1, "«Info» va inmediatamente a la derecha de «Guardar», al final de la barra"
        assert v.boton_info.text() == "Info" and v.boton_info.toolTip() == ventana_mod().AYUDA_DE_LA_INFO and v.boton_info.isEnabled()
        assert sin_simbolos(ventana_mod().AYUDA_DE_LA_INFO)
        assert v.minimumSizeHint().width() <= ALTO_Y_ANCHO[0], "con «Info» la barra cabe en los 1297 px que la ventana toma de la pantalla de 1366 x 768 del fisico"

    def test_info_abre_un_cuadro_no_modal_con_todas_las_explicaciones_una_vez(self, abierta, monkeypatch):
        v = abierta
        from PyQt5.QtWidgets import QDialog, QLabel
        monkeypatch.setattr(QDialog, "exec_", lambda *a: (_ for _ in ()).throw(AssertionError("el cuadro «Info» no se abre con exec_ (Trampa 2)")))
        pulsar(v)
        v.boton_info.click()
        QApplication.processEvents()
        d = v.dialogo_info
        assert d.isVisible() and not d.isModal() and QApplication.activeModalWidget() is None and d.parent() is v
        etiquetas = [w for w in d.findChildren(QLabel) if w.text()]
        nombres = ventana_mod().EXPLICACIONES_EN_LA_INFO
        assert etiquetas == [getattr(v, n) for n in nombres], "las cinco, en ese orden, y ninguna otra ni repetida"
        assert v.pie_de_parametros.text() == dibujo_mod().texto_de_parametros(v._resultado_en_dosis.parametros, en_la_ventana=True), "el pie es el de siempre (una sola definicion; el de la ventana dice tambien el 43)"
        assert v.linea_dosis.text().startswith("Vista en dosis [cGy].") and v.etiqueta_piso.text().startswith("Base de la medida: dosis")
        assert v.nota_pestana1.text() == dibujo_mod().nota_de_la_pestana_1(None, "G")
        v.boton_info.click()
        assert d.isVisible() and len([w for w in v.findChildren(QDialog) if w.isVisible()]) == 1, "pulsar otra vez lo trae al frente: no abre otro"
        v.boton_limpiar.click()
        assert not d.isVisible(), "una ventana nueva no tiene el cuadro abierto"

    def test_el_cuadro_info_se_cierra_con_la_ventana_y_no_reaparece_solo(self, abierta):
        """CD7-REV1-PROD-03. El cuadro es una ventana PROPIA (hija, no modal): Qt no oculta las ventanas hijas de primer nivel al ocultar a su madre, y la ventana mensual no se destruye al cerrarla (E.2 la
        guarda y la vuelve a mostrar). Sin esto el cuadro quedaba flotando solo, con los textos de una ventana cerrada, y seguia abierto al volver a mostrarla."""
        v = abierta
        d = v.dialogo_info
        v.show()
        QApplication.processEvents()
        v.boton_info.click()
        QApplication.processEvents()

        class OcultarEspontaneo(QHideEvent):
            """Lo que Qt entrega cuando es el SISTEMA quien oculta la ventana (minimizarla): su `spontaneous()` es verdadero (documentado en `QWidget.hideEvent`). No se puede provocar sin un gestor de ventanas."""
            def spontaneous(self):
                return True
        v.hideEvent(OcultarEspontaneo())
        assert d.isVisible(), "minimizar la ventana (un ocultar espontaneo) no cierra el cuadro: el sistema lo trae de vuelta con ella"
        d.hide()
        for cerrar_la_ventana in (v.close, v.hide):
            v.show()
            QApplication.processEvents()
            v.boton_info.click()
            QApplication.processEvents()
            assert v.isVisible() and d.isVisible() and d.isWindow(), "con la ventana abierta, el cuadro se ve"
            cerrar_la_ventana()
            QApplication.processEvents()
            assert not v.isVisible() and not d.isVisible(), "al cerrar u ocultar la ventana, su cuadro «Info» tambien se oculta"
            v.show()
            QApplication.processEvents()
            assert v.isVisible() and not d.isVisible(), "al volver a mostrar la ventana, el cuadro no reaparece solo"
            v.boton_info.click()
            assert d.isVisible(), "y se puede volver a abrir con su boton"
            d.hide()
        v.hide()


class TestElAltoNoCambia:
    def test_la_imagen_y_las_pestanas_no_cambian_de_alto_al_marcar_ni_al_analizar(self, fabrica, mundo, escena):
        v = fabrica(usuario=Usuario())
        v.resize(*ALTO_Y_ANCHO)
        v.show()
        assert v.cargar_imagen(escena.placa.datos, "placa_dosis.tif")
        altos = [_alto(v)]
        for k, (x, y) in enumerate(escena.clics, 1):
            clic(v, x + 80, y + 80) if k == 4 else clic(v, x, y)          # la 4 lejos de la marca: «sin refinar», el texto de las marcas gana una linea
            altos.append(_alto(v))
        assert v.estado == "analizada" and v.linea_regla.isHidden(), "la capa verde es medible: la linea de la regla no aparece"
        pulsar(v)
        altos.append(_alto(v))
        assert len(set(altos)) == 1, f"el alto de la imagen, de las pestanas y de la tabla no cambia con 0 a 5 marcas ni al pasar a dosis: {altos}"
        assert altos[0][0] >= 400, "a 1297 x 706 la imagen tiene casi todo el alto de la ventana"

    def test_los_perfiles_no_se_achican_al_pasar_a_dosis_ni_al_cambiar_la_capa(self, abierta):
        v = abierta
        v.resize(*ALTO_Y_ANCHO)
        v.show()
        v.pestanas.setCurrentIndex(2)
        antes = (v.lienzo_perfiles.parentWidget().height(), v.pestanas.height())
        pulsar(v)
        elegir = v.selector_capa
        elegir.setCurrentIndex(elegir.findData("R"))
        QApplication.processEvents()
        assert (v.lienzo_perfiles.parentWidget().height(), v.pestanas.height()) == antes

    def test_con_un_registro_abierto_tampoco_cambia_al_recalcular(self, abierta, fabrica):
        v = abierta
        v.boton_guardar.click()
        otra = fabrica(ref=v.ref, usuario=Usuario())
        otra.resize(*ALTO_Y_ANCHO)
        otra.show()
        assert otra.etiqueta_registro.isVisibleTo(otra) and otra.etiqueta_registro.window() is otra, "la linea del registro (estado, no explicacion) sigue en la ventana (CD7-D15)"
        puntos = [tuple(m["clic"]) for m in otra._registro["puntos"]]
        otra.boton_recalcular.click()
        altos = [_alto(otra)]
        for x, y in puntos:
            clic(otra, x, y)
            altos.append(_alto(otra))
        assert otra.estado == "analizada" and len(set(altos)) == 1, ("tras «Recalcular», marcar los cinco puntos no cambia ningun alto", altos)


ROTULOS_EN_NETOD = ["Capa reportada", "FWHM crossplane [mm]", "FWHM inplane [mm]", "Radiación − cruce de diagonales (x; y) [mm]", "Radiación − retículo (x; y) [mm]",
                    "Lado izquierdo (radiación − luz) [mm]", "Lado derecho (radiación − luz) [mm]", "Lado superior (radiación − luz) [mm]", "Lado inferior (radiación − luz) [mm]",
                    "Densidad óptica neta media de la meseta [1]", "Penumbra lado izquierdo, del 80 al 20 % [mm]", "Penumbra lado derecho, del 80 al 20 % [mm]",
                    "Penumbra lado superior, del 80 al 20 % [mm]", "Penumbra lado inferior, del 80 al 20 % [mm]",
                    "Largo bajo el 20 %, lado izquierdo [mm]", "Largo bajo el 20 %, lado derecho [mm]", "Largo bajo el 20 %, lado superior [mm]",
                    "Largo bajo el 20 %, lado inferior [mm]"]
ROTULOS_EN_DOSIS = ROTULOS_EN_NETOD[:9] + ["Dosis media de la meseta [cGy]", "U de la dosis de la meseta, k = 2 [cGy]"] + ROTULOS_EN_NETOD[10:]


def _esperadas(resultado, capa, meseta):
    """Las filas de la tabla, escritas AQUI desde el motor (el oraculo de `filas_de_la_capa_reportada`)."""
    m = resultado.capas[capa]
    n = dibujo_mod().numero
    par = lambda p: f"{n(p[0], 3, True)}; {n(p[1], 3, True)}"
    valores = [dibujo_mod().nombre_de_la_capa(capa), n(m.crossplane.fwhm_mm), n(m.inplane.fwhm_mm), par(m.radiacion_menos_luz_mm), par(m.radiacion_menos_reticulo_mm),
               *[n(m.coincidencia_mm[l], 3, True) for l in ("izquierdo", "derecho", "superior", "inferior")], *meseta,
               n(m.crossplane.penumbras_mm[0]), n(m.crossplane.penumbras_mm[1]), n(m.inplane.penumbras_mm[0]), n(m.inplane.penumbras_mm[1]),
               *[_largo_como_texto(getattr(m, eje), i) for eje in ("crossplane", "inplane") for i in (0, 1)]]
    return valores


class TestLaTablaDeLaImagen:
    def test_va_al_lado_de_la_imagen(self, abierta):
        v = abierta
        v.resize(*ALTO_Y_ANCHO)
        v.show()
        QApplication.processEvents()
        area = v.lienzo_imagen.parentWidget()
        izquierda = area.mapTo(v, area.rect().topLeft())
        tabla = v.tabla_desfases.mapTo(v, v.tabla_desfases.rect().topLeft())
        assert tabla.x() > izquierda.x() + area.width() - 1, "la tabla esta a la DERECHA de la imagen"
        assert abs(tabla.y() - izquierda.y()) < 60 and v.tabla_desfases.height() >= area.height() - 60, "y a su altura, no debajo"
        assert v.tabla_desfases.columnCount() == 2

    def test_en_netod_lleva_solo_los_datos_importantes_de_la_capa_reportada(self, abierta):
        v = abierta
        r = v._resultado
        filas = texto_de_la_tabla(v.tabla_desfases)
        assert [f[0] for f in filas] == ROTULOS_EN_NETOD
        m = r.capas["G"]
        netod = float(np.mean([math.log10(p.piso / p.meseta) for p in (m.crossplane, m.inplane)]))
        assert [f[1] for f in filas] == _esperadas(r, "G", [f"{netod:.3f}"])
        assert all(f[1] != "no medible" for f in filas), "en la placa de la verdad todo se mide (penumbras y largos por debajo del 20 % incluidos)"
        assert not any("Luz − retículo" in f[0] or "Piso" in f[0] for f in filas), "solo lo pedido: fuera «Luz − retículo», el piso y las notas"

    def test_sigue_al_menu_de_la_capa(self, abierta):
        v = abierta
        elegir = v.selector_capa
        elegir.setCurrentIndex(elegir.findData("R"))
        QApplication.processEvents()
        assert texto_de_la_tabla(v.tabla_desfases)[0] == ["Capa reportada", "Capa roja"]
        assert texto_de_la_tabla(v.tabla_desfases) == texto_de_la_tabla_de(dibujo_mod().filas_de_la_capa_reportada(v._resultado, "R"))

    def test_en_dosis_lleva_la_dosis_de_la_meseta_con_su_u(self, abierta):
        v = abierta
        pulsar(v)
        do = v._resultado_en_dosis
        filas = texto_de_la_tabla(v.tabla_desfases)
        assert [f[0] for f in filas] == ROTULOS_EN_DOSIS
        m = do.capas["G"]
        assert [f[1] for f in filas] == _esperadas(do, "G", [f"{m.dosis_meseta_cgy:.1f}", f"{m.u_dosis_meseta_cgy:.1f}"])
        assert abs(float(filas[1][1]) - 100.0) <= 0.05, "el FWHM crossplane en dosis es el de la verdad"

    def test_una_capa_no_medible_en_dosis_dice_su_estado_sin_numeros(self, medidos):
        filas = dibujo_mod().filas_de_la_capa_reportada(medidos.sin_azul, "B")
        assert filas == [("Capa reportada", "Capa azul"), ("Estado", medidos.sin_azul.capas["B"].estado)] and not medidos.sin_azul.capas["B"].ok

    def test_una_capa_no_medible_y_un_registro_sin_capa(self, medidos):
        r = medidos.od
        roto = dataclasses.replace(r, capas={**r.capas, "G": dataclasses.replace(r.capas["G"], estado="no medible: de prueba")})
        assert dibujo_mod().filas_de_la_capa_reportada(roto, "G") == [("Capa reportada", "Capa verde"), ("Estado", "no medible: de prueba")]
        assert dibujo_mod().filas_de_la_capa_reportada(r, None) == [] and dibujo_mod().filas_de_la_capa_reportada(r, "gris") == []

    def test_en_el_valor_de_pixel_de_antes_la_meseta_va_en_niveles(self, medidos):
        r = dataclasses.replace(medidos.od, base="valor de píxel normalizado")
        filas = dict(dibujo_mod().filas_de_la_capa_reportada(r, "G"))
        m = r.capas["G"]
        assert filas["Meseta media [nivel]"] == f"{(m.crossplane.meseta + m.inplane.meseta) / 2:.1f}" and "Densidad óptica neta media de la meseta [1]" not in filas

    def test_un_perfil_sin_meseta_la_deja_no_medible(self, medidos):
        r = medidos.od
        g = r.capas["G"]
        sin = dataclasses.replace(g, inplane=dataclasses.replace(g.inplane, meseta=None))
        filas = dict(dibujo_mod().filas_de_la_capa_reportada(dataclasses.replace(r, capas={**r.capas, "G": sin}), "G"))
        assert filas["Densidad óptica neta media de la meseta [1]"] == "no medible"


def _largo_oraculo(p, k, base="densidad óptica neta", curva=None, baja=0.2, nivel=0.02):
    """El largo por debajo de `baja` del lado `k` (0 el menor, 1 el mayor) escrito AQUI, sin las funciones del motor: la senal normalizada del perfil suavizado del motor; desde el borde de radiacion
    hacia afuera hasta el primer cruce de `baja` (interpolado); de ahi hasta el primer cruce de `nivel` (interpolado) -> (largo [mm], False); si antes llega a un dato que falta o al final, hasta la ultima
    muestra con dato -> (largo [mm], True)."""
    n = np.asarray(pm().normalizar(base, p.suavizado, p.piso, p.meseta, curva), dtype=float)
    paso = -1 if k == 0 else 1
    i = int(round(p.bordes_rad_px[k] - p.perfil.desde_px))
    while n[i + paso] > baja:
        i += paso
    x20 = i + paso * (n[i] - baja) / (n[i] - n[i + paso])
    j = i
    while 0 <= j + paso < len(n) and np.isfinite(n[j + paso]) and n[j + paso] > nivel:
        j += paso
    if not (0 <= j + paso < len(n)) or not np.isfinite(n[j + paso]):
        return abs(j - x20) * p.tam_mm, True
    return abs(j + paso * (n[j] - nivel) / (n[j] - n[j + paso]) - x20) * p.tam_mm, False


def _largo_como_texto(p, i):
    """El texto de la tabla para el largo del lado `i`, escrito AQUI: el numero, o «≥ numero (cortado por el borde)» si la pelicula se acaba antes del piso."""
    texto = dibujo_mod().numero(p.largos_bajo_la_penumbra_mm[i], 3)
    return f"≥ {texto} (cortado)" if p.largos_cortados[i] else texto


def _volver_a_medir(p, perfil=None, base="densidad óptica neta", curva=None, **cambios):
    """El mismo perfil (o `perfil`, uno recortado o con ruido) medido otra vez con el motor, con lo que el motor uso la primera vez (cruce, piso, bordes luminosos, reticulo)."""
    P = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
    P.update(cambios)
    for clave in [c for c, v in cambios.items() if v is None]:
        del P[clave]
    reticulo = None if p.exclusion_px is None else (p.exclusion_px[0] + p.exclusion_px[1]) / 2
    return pm().medir_perfil(perfil or p.perfil, p.centro_px, p.piso, base, P, p.bordes_luz_px, reticulo, curva=curva)


def _hasta_el_piso(p, rampa=120, piso=400):
    """El perfil de `p` con la pelicula mas grande: donde se acaba el dato (los NaN del borde y el final), cada lado sigue con una rampa lineal de `rampa` muestras desde la ultima muestra con dato
    hasta el piso del perfil y luego `piso` muestras en el piso. La placa de la verdad se corta antes del piso (su pelicula es chica); este perfil llega al piso en los dos lados."""
    v = p.perfil.valores
    con_dato = np.flatnonzero(np.isfinite(v))
    a, b = int(con_dato[0]), int(con_dato[-1])
    izquierda = np.concatenate([np.full(piso, p.piso), np.linspace(p.piso, v[a], rampa + 1)[:-1]])
    derecha = np.concatenate([np.linspace(v[b], p.piso, rampa + 1)[1:], np.full(piso, p.piso)])
    nuevos = np.concatenate([izquierda, v[a:b + 1], derecha])
    return dataclasses.replace(p.perfil, valores=nuevos, desde_px=p.perfil.desde_px + a - len(izquierda))


def _recortado(m, k, muestras_antes_del_piso=14):
    """El perfil de la medida `m` (que llega al piso en los dos lados) recortado del lado `k` para que la pelicula se acabe `muestras_antes_del_piso` muestras antes de donde llega al piso."""
    assert not _largo_oraculo(m, k)[1], "el perfil de partida llega al piso"
    v = m.perfil.valores
    paso = -1 if k == 0 else 1
    i = int(round(m.bordes_rad_px[k] - m.perfil.desde_px))
    n = np.asarray(pm().normalizar("densidad óptica neta", m.suavizado, m.piso, m.meseta), dtype=float)
    while n[i] > 0.02:
        i += paso
    corte = i - paso * muestras_antes_del_piso
    if k == 1:
        return dataclasses.replace(m.perfil, valores=v[:corte + 1].copy())
    return dataclasses.replace(m.perfil, valores=v[corte:].copy(), desde_px=m.perfil.desde_px + corte)


class TestElLargoBajoElVeinte:
    """Segunda pasada del ajuste (01-11, pedidos del fisico del 31-10: «el largo de la parte por debajo del 20%», «Una por lado, el largo hasta el piso solo si no se corta antes»)."""

    def test_es_uno_por_lado_desde_el_20_hasta_el_piso(self, medidos):
        P = pm().VALORES_DE_LA_GEOMETRIA
        assert P["penumbra_baja"] == 0.2 and P["nivel_de_llegada_al_piso"] == 0.02
        for capa in ("R", "G", "B", "gris"):
            for eje in ("crossplane", "inplane"):
                p = getattr(medidos.od.capas[capa], eje)
                assert p.ok and len(p.largos_bajo_la_penumbra_mm) == 2 and len(p.largos_cortados) == 2, (capa, eje)
                for k in (0, 1):
                    largo, cortado = _largo_oraculo(p, k)
                    assert abs(p.largos_bajo_la_penumbra_mm[k] - largo) <= 0.02 and p.largos_cortados[k] is cortado, (capa, eje, k, p.largos_bajo_la_penumbra_mm, largo)
                    assert p.largos_bajo_la_penumbra_mm[k] > 0
                assert p.largos_bajo_la_penumbra_mm[0] != pytest.approx(sum(p.largos_bajo_la_penumbra_mm), abs=0.01), "uno por lado: nada de sumas"

    def test_no_es_el_ancho_al_80_ni_la_penumbra(self, medidos):
        p = medidos.od.capas["G"].crossplane
        for k in (0, 1):
            assert abs(p.largos_bajo_la_penumbra_mm[k] - _largo_oraculo(p, k, baja=0.8)[0]) > 0.05, "desde el 20 %, no desde el 80 %"
            assert abs(p.largos_bajo_la_penumbra_mm[k] - p.penumbras_mm[k]) > 0.05

    def test_en_dosis_tambien_se_mide(self, medidos, escena):
        for capa in ("R", "G", "B"):
            for eje in ("crossplane", "inplane"):
                p = getattr(medidos.do.capas[capa], eje)
                curva = pm().curva_de_la_capa(escena.curva, capa)
                for k in (0, 1):
                    largo, cortado = _largo_oraculo(p, k, base="dosis", curva=curva)
                    assert p.ok and abs(p.largos_bajo_la_penumbra_mm[k] - largo) <= 0.02 and p.largos_cortados[k] is cortado, (capa, eje, k)

    def test_con_la_pelicula_mas_grande_llega_al_piso_en_los_dos_lados(self, medidos):
        for capa, eje in (("G", "crossplane"), ("B", "inplane")):
            p = getattr(medidos.od.capas[capa], eje)
            m = _volver_a_medir(p, _hasta_el_piso(p))
            assert m.ok and m.largos_cortados == (False, False), (capa, eje, m.largos_cortados)
            for k in (0, 1):
                largo, cortado = _largo_oraculo(m, k)
                assert not cortado and abs(m.largos_bajo_la_penumbra_mm[k] - largo) <= 0.02, (capa, eje, k, m.largos_bajo_la_penumbra_mm, largo)
                assert m.largos_bajo_la_penumbra_mm[k] >= p.largos_bajo_la_penumbra_mm[k] - 1e-9, "la placa chica se corta antes: su largo es una cota menor"
            assert m.fwhm_mm == pytest.approx(p.fwhm_mm, abs=1e-9) and m.penumbras_mm == pytest.approx(p.penumbras_mm, abs=1e-9), "ninguna otra medida cambia"

    def test_la_placa_chica_se_corta_y_lo_marca(self, medidos):
        cortados = [getattr(medidos.od.capas[c], e).largos_cortados for c in ("R", "G", "B") for e in ("crossplane", "inplane")]
        assert any(True in par for par in cortados), "la placa de la verdad se acaba antes del piso en algun lado: el caso cortado sale del motor"

    def test_un_lado_cortado_por_el_borde_lo_marca_y_el_otro_no(self, medidos):
        g = medidos.od.capas["G"].crossplane
        p = _volver_a_medir(g, _hasta_el_piso(g))
        for k in (0, 1):
            m = _volver_a_medir(p, _recortado(p, k))
            assert m.ok, m.estado
            assert m.largos_cortados[k] is True and m.largos_cortados[1 - k] is False, m.largos_cortados
            largo, cortado = _largo_oraculo(m, k)
            assert cortado and abs(m.largos_bajo_la_penumbra_mm[k] - largo) <= 0.02, (m.largos_bajo_la_penumbra_mm, largo)
            assert m.largos_bajo_la_penumbra_mm[k] < p.largos_bajo_la_penumbra_mm[k], "hasta el borde: una cota menor que el largo hasta el piso"
            assert abs(m.largos_bajo_la_penumbra_mm[1 - k] - p.largos_bajo_la_penumbra_mm[1 - k]) <= 1e-9, "el otro lado no cambia"
            assert m.fwhm_mm == pytest.approx(p.fwhm_mm, abs=1e-9) and m.penumbras_mm == pytest.approx(p.penumbras_mm, abs=1e-9)

    def test_con_ruido_sigue_al_oraculo(self, medidos):
        g = medidos.od.capas["G"].inplane
        p = _volver_a_medir(g, _hasta_el_piso(g))
        ruido = np.random.default_rng(7).normal(0.0, 0.6, len(p.perfil.valores))
        m = _volver_a_medir(p, dataclasses.replace(p.perfil, valores=p.perfil.valores + ruido))
        for k in (0, 1):
            largo, cortado = _largo_oraculo(m, k)
            assert m.ok and abs(m.largos_bajo_la_penumbra_mm[k] - largo) <= 0.02 and m.largos_cortados[k] is cortado

    def test_los_bordes_de_la_cuenta_un_cruce_justo_en_una_muestra_y_un_hueco(self):
        """`_largo_hasta_el_piso` con perfiles escritos a mano (largos en muestras, calculados AQUI): el 20 % cae justo en una muestra; el piso se interpola; un hueco corta; los dos sentidos."""
        largo = pm()._largo_hasta_el_piso
        n = np.array([1.0, 0.5, 0.2, 0.1, 0.0, 0.0])
        assert largo(n, 2.0, 1, 0.2, 0.02) == pytest.approx((1.8, False))          # del 20 % (muestra 2) al 2 % entre 3 (0.1) y 4 (0.0): 3.8 - 2.0
        assert largo(n[::-1].copy(), 3.0, -1, 0.2, 0.02) == pytest.approx((1.8, False))
        hueco = np.array([1.0, 0.5, 0.2, 0.1, np.nan, 0.0])
        assert largo(hueco, 2.0, 1, 0.2, 0.02) == pytest.approx((1.0, True))       # hasta la ultima muestra con dato (3), marcado
        assert largo(np.array([1.0, 0.5, 0.15, 0.1, 0.08]), 1.875, 1, 0.2, 0.02) == pytest.approx((4 - 1.875, True))      # sin llegar al piso ni hueco: hasta el final

    def test_el_piso_es_el_parametro_43_y_un_registro_sin_el_se_mide_con_el_de_fabrica(self, medidos):
        p = medidos.od.capas["G"].crossplane
        nombre = "nivel_de_llegada_al_piso"
        entrada = pm().PARAMETROS[nombre]
        assert entrada["valor"] == 0.02 and entrada["unidad"] == "fracción" and len(entrada["motivo"]) > 100
        assert list(pm().VALORES_DE_LA_GEOMETRIA)[-1] == nombre and len(pm().VALORES_DE_LA_GEOMETRIA) == 43
        assert nombre not in pm().CLAVES_QUE_PIDE_LA_MEDIDA and nombre not in pm().CLAVES_QUE_PIDE_ANALIZAR
        assert medidos.od.parametros[nombre] == 0.02, "un analisis nuevo lo lleva con sus parametros (se guarda con ellos)"
        p = _volver_a_medir(p, _hasta_el_piso(p))
        viejo = _volver_a_medir(p, **{nombre: None})
        assert viejo.largos_bajo_la_penumbra_mm == p.largos_bajo_la_penumbra_mm and viejo.largos_cortados == p.largos_cortados
        alto = _volver_a_medir(p, **{nombre: 0.05})
        for k in (0, 1):
            assert alto.largos_bajo_la_penumbra_mm[k] < p.largos_bajo_la_penumbra_mm[k] - 0.02
            assert abs(alto.largos_bajo_la_penumbra_mm[k] - _largo_oraculo(p, k, nivel=0.05)[0]) <= 0.02

    def test_el_43_se_dice_en_el_cuadro_info_y_no_en_el_pie_del_pdf(self, medidos):
        frase = "el largo por debajo del 20 % llega al piso donde la señal baja al 2 %"
        assert dibujo_mod().TRAZO_DE_PARAMETRO["nivel_de_llegada_al_piso"][0] == "largo"
        assert frase in dibujo_mod().texto_de_parametros(medidos.od.parametros, en_la_ventana=True)
        assert frase not in dibujo_mod().texto_de_parametros(medidos.od.parametros) and frase not in dibujo_mod().texto_de_parametros()
        sin_el = {c: v for c, v in medidos.od.parametros.items() if c != "nivel_de_llegada_al_piso"}
        assert frase in dibujo_mod().texto_de_parametros(sin_el, en_la_ventana=True), "un registro de antes de CD.7 se midio con el de fabrica"
        assert dibujo_mod().texto_de_parametros(sin_el) == dibujo_mod().texto_de_parametros(medidos.od.parametros)

    def test_la_frase_del_43_dice_el_valor_con_que_se_midio_sin_redondearlo_a_un_entero(self):
        """CD7-REV1-PROD-04. La frase se formateaba con «{:.0%}»: 0.025 y 0.015 salian como «2%», y el 43 es justamente lo que PA-1 le deja abierto al fisico (PD1: el pie dice el valor con que se midio). Ahora lleva
        el porcentaje exacto y, como el resto de la ventana («del 20 %»), un espacio antes del «%»."""
        d = dibujo_mod()
        for valor, dicho in ((0.02, "2 %"), (0.025, "2.5 %"), (0.015, "1.5 %"), (0.03, "3 %"), (0.05, "5 %"), (0.1, "10 %"), (0.07, "7 %")):
            P = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
            P["nivel_de_llegada_al_piso"] = valor
            texto = d.texto_de_parametros(P, en_la_ventana=True)
            assert f"el largo por debajo del 20 % llega al piso donde la señal baja al {dicho} (si la película se acaba antes, se marca cortado por el borde)" in texto, (valor, texto[-160:])
        P = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
        del P["nivel_de_llegada_al_piso"]
        assert "baja al 2 % (si la película se acaba antes" in d.texto_de_parametros(P, en_la_ventana=True), "un registro de antes de CD.7 se midio con el de fabrica, 2 %"

    def test_el_motivo_del_43_dice_en_que_modo_del_piso_se_midio_cada_cifra(self):
        """CD7-REV1-PROD-01 y PROD-05. Las cifras que sostienen el parametro 43 (y la pregunta PA-1 al fisico) se midieron con el piso «automatico» (las esquinas), pero la ventana mide POR OMISION con la
        pelicula virgen cargada (DA-88): ahi el largo casi nunca llega al piso (1 de 64 lados con el 2 %, 6 con el 5 %) y subir el nivel no lo arregla. El motivo dice las cifras de los DOS modos, el
        de la ventana primero, y el rango de los lados cortados es el de los cortados (de 1.6 a 9.2 mm; 10.2 mm era el maximo de los 64 lados, incluidos los que si llegan)."""
        motivo = pm().PARAMETROS["nivel_de_llegada_al_piso"]["motivo"]
        assert pel().MODO_DEL_PISO_POR_OMISION == "virgen", "si el modo de omision cambia, las cifras del motivo hay que volver a medirlas"
        assert "película virgen" in motivo and "«automático»" in motivo and "por omisión" in motivo and "EPSON179" in motivo, motivo
        assert motivo.index("película virgen") < motivo.index("«automático»"), "primero el modo con que arranca la ventana"
        assert "1.6 a 9.2 mm" in motivo and "1.6 a 10.2" not in motivo, "los lados cortados miden de 1.56 a 9.20 mm; 10.16 es el maximo de los 64 lados"
        assert "casi siempre" in motivo and "no lo arregla" in motivo, "con la virgen cargada el largo sale casi siempre como cota y subir el nivel no lo cambia"

    def test_el_cuadro_info_de_la_ventana_lo_dice_con_el_valor_del_analisis(self, abierta):
        assert "el largo por debajo del 20 % llega al piso donde la señal baja al 2 %" in abierta.pie_de_parametros.text()
        assert abierta.pie_de_parametros.text() == dibujo_mod().texto_de_parametros(abierta._resultado.parametros, en_la_ventana=True)

    def test_a_1297_por_706_la_tabla_se_lee_entera(self, abierta):
        """La ventana en la pantalla de 1366 x 768 del fisico: ningun rotulo ni valor de la tabla de la pestana 1 queda cortado (medido el 01-11: con el reparto 3 a 2 el valor «≥ 3.389 (cortado)» no cabia)."""
        v = abierta
        v.resize(1297, 706)
        v.show()
        QApplication.processEvents()
        t = v.tabla_desfases
        fm = t.fontMetrics()
        assert t.rowCount() == 18
        for i in range(t.rowCount()):
            for j in (0, 1):
                texto = t.item(i, j).text()
                assert fm.horizontalAdvance(texto) + 4 <= t.columnWidth(j), (i, j, texto, t.columnWidth(j))      # Qt deja ~7 px de margen en la celda
        assert t.horizontalScrollBar().maximum() == 0, "sin barra horizontal"

    def test_la_tabla_dice_el_rotulo_y_cortado_y_no_el_nombre_del_80(self, medidos):
        r = medidos.od
        g = r.capas["G"]
        cortada = dataclasses.replace(g, crossplane=dataclasses.replace(g.crossplane, largos_bajo_la_penumbra_mm=(1.23456, 4.5), largos_cortados=(True, False)),
                                      inplane=dataclasses.replace(g.inplane, largos_bajo_la_penumbra_mm=(None, 2.0), largos_cortados=(None, False)))
        filas = dict(dibujo_mod().filas_de_la_capa_reportada(dataclasses.replace(r, capas={**r.capas, "G": cortada}), "G"))
        assert filas["Largo bajo el 20 %, lado izquierdo [mm]"] == "≥ 1.235 (cortado)"
        assert filas["Largo bajo el 20 %, lado derecho [mm]"] == "4.500"
        assert filas["Largo bajo el 20 %, lado superior [mm]"] == "no medible"
        assert filas["Largo bajo el 20 %, lado inferior [mm]"] == "2.000"
        assert dibujo_mod().ROTULO_DEL_LARGO.format(baja=20, lado="izquierdo") == "Largo bajo el 20 %, lado izquierdo [mm]"
        for resultado in (medidos.od, medidos.do):
            for rotulo, valor in dibujo_mod().filas_de_la_capa_reportada(resultado, "G"):
                assert "mbra" not in rotulo.replace("Penumbra", "") and "mbra" not in valor, rotulo
        assert sum(1 for rotulo in filas if rotulo.startswith("Largo bajo el")) == 4

    def test_es_aditivo_no_va_en_lo_guardado_ni_cambia_la_version(self, medidos):
        p = medidos.od.capas["G"].crossplane
        assert "largos_bajo_la_penumbra_mm" not in p.como_dict() and "largos_cortados" not in p.como_dict()
        assert dataclasses.replace(p, largos_bajo_la_penumbra_mm=None, largos_cortados=None).como_dict() == p.como_dict()
        assert pm().VERSION_ALGORITMO == "PM-1"
        assert "largos_" not in str(medidos.od.capas["G"].como_dict())

    def test_un_perfil_no_medible_no_tiene_largos(self, medidos):
        vacia = pm()._sin_medir_la_capa("G", "no medible: de prueba", 0.042)
        assert vacia.crossplane.largos_bajo_la_penumbra_mm is None and vacia.inplane.largos_cortados is None


class TestSinElGris:
    def test_ninguna_pestana_muestra_el_gris(self, abierta):
        v = abierta
        for vista in ("netOD", "dosis"):
            assert not any(hasattr(v, n) for n in ("_fig_gris", "lienzo_gris", "barra_gris")), "la pestana 1 ya no tiene los perfiles del gris"
            titulos = [ax.get_title() for ax in v._fig_perfiles.axes]
            assert len(v._fig_perfiles.axes) == 6 and not any(t.startswith("Gris") for t in titulos), (vista, titulos)
            assert not any(f[0] == "Gris" for f in texto_de_la_tabla(v.tabla_perfiles)) and not any(f[0] == "Gris" for f in texto_de_la_tabla(v.tabla_barridos))
            gids = [str(l.get_gid()) for ax in v._fig_barridos.axes for l in ax.lines]
            assert not any(g.endswith(":gris") for g in gids) and not any("gris" == str(l.get_label()) for ax in v._fig_barridos.axes for l in ax.lines)
            assert all("gris" not in t.lower() for t in todos_los_textos(v) if t not in (v.pie_de_parametros.text(), v.etiqueta_piso.text())), "ningun texto de la ventana habla del gris (los parametros del motor si)"
            pulsar(v)

    def test_el_motor_sigue_midiendo_el_gris(self, abierta):
        assert abierta._resultado.capas["gris"].ok, "los clics se refinan sobre el gris: el motor lo sigue midiendo, no se muestra"


class TestLaCuadraturaContra100:
    def test_los_lados_se_comparan_con_100_mm_y_las_diagonales_con_100_por_raiz_de_2(self, abierta):
        d = dibujo_mod()
        assert d.LADO_DEL_CUADRADO_PERFECTO_MM == 100.0 and not hasattr(d, "lado_perfecto_mm")
        g = abierta._resultado.geometria
        filas = d.filas_de_la_cuadratura(g)
        lados = [f for f in filas if f[0].startswith("Lado ")]
        diagonales = [f for f in filas if f[0].startswith("Diagonal")]
        assert len(lados) == 4 and all(f[2] == "100.000" for f in lados), lados
        assert len(diagonales) == 2 and all(f[2] == f"{100 * math.sqrt(2):.3f}" for f in diagonales), diagonales
        # CD7-REV1-R1-P4: la columna «Diferencia» tambien es contra el cuadrado perfecto (medido menos 100 y menos 100 x raiz de 2), escrita AQUI desde la geometria del motor; antes solo se miraba la columna del ideal
        # y un ideal de 100 con la diferencia contra la media de los lados medidos pasaba toda la prueba
        assert {f[0]: f[3] for f in lados} == {f"Lado {n} [mm]": d.numero(v - 100.0, 3, True) for n, v in g.lados_mm.items()}, lados
        assert [f[3] for f in diagonales] == [d.numero(v - 100.0 * math.sqrt(2.0), 3, True) for v in g.diagonales_mm], diagonales

    def test_el_cuadrado_ideal_no_cambia_con_los_lados_medidos(self, abierta):
        d = dibujo_mod()
        g = abierta._resultado.geometria
        otra = dataclasses.replace(g, lados_mm={k: v + 3.0 for k, v in g.lados_mm.items()})
        assert [f[2] for f in d.filas_de_la_cuadratura(otra)] == [f[2] for f in d.filas_de_la_cuadratura(g)], "el ideal no depende de lo medido"
        # CD7-REV1-R1-P4: y la diferencia SI se mueve con lo medido: todos los lados 3 mm mas largos son 3 mm mas de diferencia contra los 100 mm (contra la media de los lados medidos no cambiaria: el corrimiento comun se cancela)
        antes, despues = d.filas_de_la_cuadratura(g), d.filas_de_la_cuadratura(otra)
        for f0, f1 in zip(antes[:4], despues[:4]):
            assert float(f1[3]) - float(f0[3]) == pytest.approx(3.0, abs=2.1e-3), (f0, f1)
        assert [f[3] for f in despues[4:]] == [f[3] for f in antes[4:]], "las inclinaciones, los angulos y las diagonales no dependen de los lados"
        assert d.cuadrado_perfecto() == [(-50.0, -50.0), (50.0, -50.0), (50.0, 50.0), (-50.0, 50.0)] or sorted(map(tuple, np.abs(d.cuadrado_perfecto()).tolist())) == [(50.0, 50.0)] * 4

    def test_la_leyenda_dice_100_mm(self, abierta):
        v = abierta
        etiquetas = [str(l.get_label()) for l in v.eje_cuadratura.lines]
        assert any("cuadrado perfecto de 100 mm" in e for e in etiquetas), etiquetas
