"""B.7 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-85, PD1): el menu «Capa reportada» de la pagina de la posicion inicial de braquiterapia.

CAUSA. El fisico pidio el 11-10 poder elegir en la app con que capa (rojo, verde o azul) se reportan las medidas. Hasta B.6 la pagina no tenia donde elegir: el resultado completo (desfase +- U, sentido, veredicto) solo
se mostraba del GRIS, la pestana de capas daba una linea por capa, la confirmacion de Guardar avisaba si el GRIS no se pudo medir y `_al_guardar` no pasaba ninguna capa al servicio (B.5 la guarda, B.6 la imprime): un
registro guardado desde la pantalla quedaba sin capa y el PDF lo imprimia con el gris. La eleccion es del fisico (PD3) y tiene que VERSE, GUARDARSE e IMPRIMIRSE (PD1): asi no mueve un numero a escondidas.

Que fija este archivo (todo POR EL CAMINO DEL USUARIO: la pagina real, el boton «Guardar» real, el escritor real del servicio y una BD temporal; nunca una BD de referencia):
  1. EL MENU. Ofrece exactamente rojo, verde y azul (`NOMBRE_DE_CAPA` en el orden de `CAPAS`, la letra como dato), arranca en `CAPA_POR_OMISION` (la constante, no una letra escrita a mano), no cambia con la rueda del raton
     sin foco (PI.4), tiene su rotulo y UNA conexion, va en la fila de los botones sin empujar ni tapar ninguno (a 1500, 1100, 850 y 750 px) y no agranda el ancho minimo de la pagina.
  2. ELEGIR UNA CAPA MUESTRA SU RESULTADO. El recuadro de las capas empieza por el resultado COMPLETO de la capa elegida con los numeros del MOTOR de esa capa (oraculo propio: `valores_medidos` y `resumen`) y su nombre, y
     debajo siguen las tres lineas de siempre; el recuadro del gris conserva el resultado del gris y anade la linea que dice que capa se reporta; el perfil de la capa elegida se rotula «reportada» y los otros dos no.
     CAMBIAR EL MENU NO RECALCULA NADA (espias sobre el servicio, el motor y la medida de un perfil: cero llamadas), no redibuja los datos (el zoom del fisico se conserva) y converge con elegir la capa antes de analizar.
  3. GUARDAR. Sin tocar el menu guarda la capa por omision; con el escritor real guarda `capa_reportada` = la elegida (R, G y B) y la fila de auditoria la nombra; la llamada al servicio lleva la LETRA de `pelicula.CAPAS`;
     la confirmacion avisa si la capa ELEGIDA no se pudo medir (no el gris) y la nombra; por AST la llamada de la pagina a `svc.guardar` pasa `capa_reportada`.
  4. REABRIR. Pone el menu en la capa guardada con las senales bloqueadas; un registro sin capa (anterior a B.5 o a B.7) deja el menu en la capa por omision y lo dice en la etiqueta; una capa guardada invalida no abre
     el registro a medias.
  5. LA TABLA DE REGISTROS. Gana la columna «Capa» DESPUES de «Resultado» (las cuatro primeras siguen donde estan), con el color de cada registro (vacia si no tiene capa), y el desfase de cada fila es el de la capa de ese registro.
  6. LIMPIAR devuelve el menu a la capa por omision (la huella de «recien creada» lo incluye); Recalcular y cargar otra imagen conservan la eleccion; cambiar el menu sin guardar no cambia nada de lo guardado.
  7. POR AST: la pagina no escribe las tres capas a mano (lee `pelicula.CAPAS`), lee `CAPA_POR_OMISION` solo como valor inicial del menu, y el titulo de un perfil se define UNA vez (`titulo_del_perfil`).
  8. (RONDA 1 DE REVISION, 17-10, B7-C1) CON UN REGISTRO GUARDADO O ABIERTO la capa que la pantalla reporta es la que GUARDO ese registro: el menu queda fijo (como Guardar), moverlo por codigo no cambia ni un recuadro ni un titulo,
     lo que dice la pantalla es lo que imprime el PDF y lo que dice la columna «Capa»; un registro SIN capa no afirma ninguna (los recuadros son los de siempre). Y los huecos de pruebas que la revision demostro con mutaciones: el
     NUMERO del titulo de cada perfil (la fila del gris), su tamano de letra, abrir un registro cuyo analisis falla (el menu no se mueve), «Resultado» toma lo que sobra, el guardia de las tres capas a mano ve listas y «RGB».
Trampa 2 (todo QMessageBox y dialogo se parcha: la fixture `dialogos` de PI.4), Trampa 9 (las paginas se cierran con la receta completa: la fixture `fabrica`; ninguna huella mira internos de Qt), Trampa 10 (ningun
`lru_cache`; los resultados caros son fixtures de modulo y nadie los muta)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
from pathlib import Path

import pytest
from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QComboBox, QMessageBox

import ui.paginasControles.PruebasMensuales.posicion_inicial_braqui as pagina_mod
from analisisImagenes import dibujo_posicion_inicial as dibujo
from analisisImagenes import pelicula as pel
from analisisImagenes import posicion_inicial_braqui as motor
from services import posicion_inicial_braqui as svc
from test_pi1_motor_posicion_inicial import CLICS_EPSON009, CLICS_PLACA_REAL
from test_pi3_servicio_posicion_inicial import (BRAQUI_00, EPSON009, USUARIO, _auditoria, _consulta, _filas, bd,  # noqa: F401  (fixtures de PI.3)
                                                plantilla)
from test_pi4_pagina_posicion_inicial import (CAMBIO, CLICS_LINEA_ALEJADA, SERIE_C, TABLA, _analizada, _cargar, _con_mtime,  # noqa: F401  (fixtures y ayudas de PI.4)
                                              _cursor_limpio, _huella, _marcar, _texto_sin_simbolos, app, archivo_braqui, dialogos, fabrica,
                                              pagina)

RAIZ = Path(__file__).resolve().parent.parent
PAGINA_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "posicion_inicial_braqui.py"
DIBUJO_PY = RAIZ / "analisisImagenes" / "dibujo_posicion_inicial.py"

# Los oraculos de ESTE archivo estan escritos aqui, a mano, y no salen de las tablas de produccion (R1-PROD-01 de B.6: una prueba que usa la propia constante como oraculo no ve que la constante este mal).
COLOR = {"R": "rojo", "G": "verde", "B": "azul"}                # lo que dice un MENU o una columna: el color a secas
ADJETIVO = {"R": "roja", "G": "verde", "B": "azul"}             # lo que dice una FRASE con «capa»: concuerda con el sustantivo
CAPAS = ("R", "G", "B")
OTRA_CAPA = {"R": "G", "G": "B", "B": "R"}                      # una capa distinta de la dada (para dejar el menu en otro sitio)


# ------------------------------------------------------------------------------------------------------ fixtures y ayudas

@pytest.fixture(scope="module")
def epson():
    """EPSON009 con los clics de la suite: las TRES capas se miden y dan numeros distintos (R +0.162, G -0.097, B -0.142 mm), de modo que cruzar dos capas se ve."""
    return svc.analizar_imagen(EPSON009, CLICS_EPSON009)


@pytest.fixture(scope="module")
def braqui_00():
    """La placa real del plan: el gris, el verde y el azul se miden y la ROJA no (la mancha esta cortada por el borde de la pelicula)."""
    return svc.analizar_imagen(BRAQUI_00, CLICS_PLACA_REAL)


@pytest.fixture
def archivo_epson(tmp_path):
    return _con_mtime(tmp_path, "EPSON009.jpeg", 2026, 9, 30)


@pytest.fixture
def espias_del_motor(monkeypatch):
    """Cuenta las llamadas a lo que MIDE: el servicio que analiza, el motor y la medida de un perfil. Cambiar de capa no puede llamar a ninguna."""
    llamadas = {"servicio.analizar_imagen": 0, "motor.analizar": 0, "motor.medir_perfil": 0}
    for modulo, nombre, clave in ((svc, "analizar_imagen", "servicio.analizar_imagen"), (motor, "analizar", "motor.analizar"), (motor, "medir_perfil", "motor.medir_perfil")):
        def espia(*a, _real=getattr(modulo, nombre), _clave=clave, **k):
            llamadas[_clave] += 1
            return _real(*a, **k)
        monkeypatch.setattr(modulo, nombre, espia)
    return llamadas


def _elegir(p, capa):
    """El fisico abre el menu y elige esa capa (el mismo `currentIndexChanged` que emite un clic en la lista)."""
    p.selector_capa.setCurrentIndex(CAPAS.index(capa))


def _cabeza_y_cola(texto):
    """El recuadro de las capas: (el bloque de la capa elegida, las tres lineas de siempre), separados por UNA linea en blanco."""
    partes = texto.split("\n\n")
    assert len(partes) == 2, f"el recuadro de las capas tiene {len(partes)} bloques separados por una linea en blanco: {texto!r}"
    return partes[0], partes[1]


def _lineas_de_una_capa_medida(resultado, capa):
    """El ORACULO de lo que el recuadro dice de una capa medida: sale del motor (`valores_medidos`, `resumen`), no de la pagina."""
    s, v, r = capa.lower(), motor.valores_medidos(resultado), motor.resumen(resultado, capa)
    assert v[f"estado_{s}"] == "ok", f"la capa {capa} de esta pelicula no se mide: elija otra"
    assert resultado["parametros"]["tolerancia_mm"] == 1.0
    lado = resultado["lado_transito"]
    return [f"Desfase en la imagen: {v[f'desfase_{s}_px']:.2f} px = {v[f'desfase_{s}_mm']:.3f} mm",
            f"Incertidumbre (k = 2): {r['U_mm']:.2f} mm = {v[f'incertidumbre_{s}_px']:.2f} px ({v[f'filas_{s}']} cuerdas)",
            f"La fuente quedó {abs(r['desfase_fisico_mm']):.2f} mm {r['sentido']} (banda de tránsito a la {lado} de la imagen, {resultado['contrastes_transito'][lado]['contraste']:.0f} niveles)",
            f"Tolerancia 1.0 mm: {r['veredicto']}"]


def _con_estado_del_gris(resultado, estado):
    """Una copia SUPERFICIAL del resultado con otro estado del gris (para las funciones puras: no se vuelve a analizar nada)."""
    perfiles = {**resultado["perfiles"], "gris": {**resultado["perfiles"]["gris"], "estado": estado}}
    return {**resultado, "perfiles": perfiles}


def _lo_que_la_pantalla_dice(p):
    """Todo lo que la pagina afirma de la capa reportada: los dos recuadros y el titulo de los tres perfiles de las capas."""
    return p.recuadro_gris.text(), p.recuadro_rgb.text(), tuple(e.get_title() for e in p._fig_rgb.axes[:3])


def _capa_que_dice_la_pantalla(p):
    """La letra de la capa que la cabeza del recuadro de las capas dice que se reporta (None si no dice ninguna)."""
    primera = p.recuadro_rgb.text().split("\n")[0]
    if not primera.startswith("Capa reportada: "):
        return None
    color = primera[len("Capa reportada: "):]
    return next(c for c in CAPAS if COLOR[c] == color)


def _capa_que_imprime_el_pdf(fecha):
    """La letra de la capa con que el servicio arma la linea de los PDF de esa fecha (None si imprime el gris de siempre, sin el prefijo «Capa ...: »)."""
    texto = svc.texto_para_pdf(fecha)
    for c in CAPAS:
        if texto.startswith(f"Capa {ADJETIVO[c]}: "):
            return c
    assert not texto.startswith("Capa "), texto
    return None


def _las_tres_capas_a_mano(arbol):
    """[(linea, forma)] de cada sitio donde un arbol escribe las tres capas a mano en vez de leer `pelicula.CAPAS`: una tupla, lista o conjunto de EXACTAMENTE las constantes R, G y B (en cualquier orden), un diccionario con
    esas tres claves o la cadena «RGB» (que se recorre letra a letra). Una comparacion suelta (`== "R"`) o una coleccion con otros elementos (los ejes: R, G, B y el barrido; el barrido: gris, R, G, B) no cuentan."""
    sitios = []
    for n in ast.walk(arbol):
        if isinstance(n, (ast.Tuple, ast.List, ast.Set)):
            valores = [e.value for e in n.elts if isinstance(e, ast.Constant)]
            if len(n.elts) == 3 and len(valores) == 3 and set(valores) == {"R", "G", "B"}:
                sitios.append((n.lineno, type(n).__name__))
        elif isinstance(n, ast.Dict):
            claves = [k.value for k in n.keys if isinstance(k, ast.Constant)]
            if len(n.keys) == 3 and len(claves) == 3 and set(claves) == {"R", "G", "B"}:
                sitios.append((n.lineno, "Dict"))
        elif isinstance(n, ast.Constant) and n.value == "RGB":
            sitios.append((n.lineno, "cadena"))
    return sitios


# ================================================================================================= 1. el menu en la barra

class TestElMenuEnLaBarra:
    def test_ofrece_rojo_verde_y_azul_con_la_letra_de_cada_capa_como_dato(self, pagina):
        combo = pagina.selector_capa
        assert combo.count() == 3, "el gris no se ofrece (DA-85): solo las tres capas de color"
        assert [combo.itemText(i) for i in range(combo.count())] == ["rojo", "verde", "azul"]
        assert [combo.itemData(i) for i in range(combo.count())] == ["R", "G", "B"], "la letra es lo que viaja al servicio (`pelicula.CAPAS`)"
        assert not combo.isEditable()

    def test_arranca_en_la_capa_por_omision(self, pagina):
        assert pel.CAPA_POR_OMISION == "G", "premisa: la capa por omision es la verde"
        assert pagina.capa_reportada == "G" and pagina.selector_capa.currentText() == "verde"

    @pytest.mark.parametrize("otra", ["R", "B"])
    def test_arranca_en_lo_que_diga_la_constante_y_no_en_una_letra_escrita_a_mano(self, fabrica, monkeypatch, otra):
        monkeypatch.setattr(pagina_mod, "CAPA_POR_OMISION", otra)
        p = fabrica()
        assert p.capa_reportada == otra and p.selector_capa.currentText() == COLOR[otra]

    def test_es_un_selector_sin_rueda_y_se_deja_enfocar_con_el_teclado(self, pagina):
        assert type(pagina.selector_capa).__name__ == "_SelectorSinRueda" and isinstance(pagina.selector_capa, QComboBox)
        assert pagina.selector_capa.focusPolicy() == Qt.StrongFocus

    @pytest.mark.parametrize("capa_inicial", CAPAS)
    def test_la_rueda_del_raton_no_cambia_la_capa_si_el_menu_no_tiene_el_foco(self, pagina, capa_inicial):
        _elegir(pagina, capa_inicial)
        assert not pagina.selector_capa.hasFocus()
        rueda = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), 0, Qt.Vertical, Qt.NoButton, Qt.NoModifier)
        QApplication.sendEvent(pagina.selector_capa, rueda)
        assert pagina.capa_reportada == capa_inicial and not rueda.isAccepted(), \
            "un paso de la rueda al pasar por la pagina cambiaria lo que se reporta y se guarda"

    def test_una_tecla_del_teclado_si_cambia_la_capa(self, pagina):
        """El camino del teclado (el menu tiene foco fuerte): la flecha abajo pasa de verde a azul y la pagina se entera."""
        assert pagina.capa_reportada == "G"
        QTest.keyClick(pagina.selector_capa, Qt.Key_Down)
        assert pagina.capa_reportada == "B"

    def test_tiene_su_rotulo_su_ayuda_y_una_sola_conexion(self, pagina):
        assert pagina.etiqueta_capa.text() == "Capa reportada:"
        assert pagina.etiqueta_capa.buddy() is pagina.selector_capa, "el rotulo se asocia al menu (accesibilidad)"
        assert pagina.selector_capa.toolTip(), "el menu dice para que sirve"
        assert pagina.selector_capa.receivers(pagina.selector_capa.currentIndexChanged) == 1, \
            "una conexion por senal (una de mas actualizaria dos veces; una de menos dejaria el menu mudo)"

    @pytest.mark.parametrize("ancho,alto", [(1500, 750), (1100, 800), (850, 800), (750, 800)])
    def test_va_en_la_fila_de_los_botones_y_no_empuja_ni_tapa_ninguno(self, pagina, ancho, alto):
        pagina.resize(ancho, alto)
        pagina.show()
        QApplication.processEvents()
        fila = [pagina.boton_recalcular, pagina.boton_limpiar, pagina.boton_guardar, pagina.boton_anular, pagina.etiqueta_capa, pagina.selector_capa]
        cajas = [w.geometry() for w in fila]
        for w, caja in zip(fila, cajas):
            assert caja.width() >= w.minimumSizeHint().width(), f"{type(w).__name__} quedo mas angosto que su minimo: {caja.width()} < {w.minimumSizeHint().width()} a {ancho} px"
            assert caja.left() >= 0 and caja.right() <= pagina.width(), "queda dentro de la pagina"
        for i in range(len(cajas)):
            for j in range(i + 1, len(cajas)):
                assert not cajas[i].intersects(cajas[j]), f"un widget de la fila se encima con otro a {ancho} px: {cajas[i]} {cajas[j]}"
        assert cajas[3].right() < cajas[4].left() < cajas[5].left(), "el orden es: los cuatro botones, el rotulo, el menu"
        assert max(c.top() for c in cajas) < min(c.bottom() for c in cajas), "los seis estan en UNA fila (no baja a otra linea)"

    def test_no_agranda_el_ancho_minimo_de_la_pagina(self, pagina):
        pagina.resize(1300, 900)
        pagina.show()
        QApplication.processEvents()
        con = pagina.minimumSizeHint().width()
        pagina.etiqueta_capa.hide()
        pagina.selector_capa.hide()
        pagina.layout().invalidate()
        pagina.layout().activate()
        sin = pagina.minimumSizeHint().width()
        assert con == sin, f"el menu agranda el ancho minimo de la pagina de {sin} a {con} px (la ventana principal no podria estrecharse)"


# ================================================================================ 2. elegir una capa muestra el resultado de esa capa

class TestElegirUnaCapaMuestraSuResultado:
    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_recuadro_de_las_capas_empieza_por_la_capa_elegida_con_los_numeros_del_motor_de_esa_capa(self, pagina, dialogos, archivo_epson, epson, capa):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(pagina, capa)
        cabeza, _cola = _cabeza_y_cola(pagina.recuadro_rgb.text())
        lineas = cabeza.split("\n")
        esperadas = [f"Capa reportada: {COLOR[capa]}", *_lineas_de_una_capa_medida(epson, capa)]
        assert lineas[:len(esperadas)] == esperadas, "\n" + "\n".join(lineas) + "\n--- esperadas:\n" + "\n".join(esperadas)
        assert all(l.startswith("Resolución: ") for l in lineas[len(esperadas):]), "lo que sigue es la nota de resolucion de EPSON009, nada de otra capa"
        v = motor.valores_medidos(epson)
        for otra in CAPAS:
            if otra != capa:
                assert f"Desfase en la imagen: {v[f'desfase_{otra.lower()}_px']:.2f} px" not in cabeza, f"el bloque de la capa {capa} lleva los numeros de la {otra}"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_debajo_siguen_las_tres_lineas_de_siempre_sea_cual_sea_la_capa_elegida(self, pagina, dialogos, archivo_epson, epson, capa):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(pagina, capa)
        _cabeza, cola = _cabeza_y_cola(pagina.recuadro_rgb.text())
        v = motor.valores_medidos(epson)
        assert cola.split("\n") == [f"Capa {c}: desfase en la imagen {v[f'desfase_{c.lower()}_px']:.2f} px = {v[f'desfase_{c.lower()}_mm']:.3f} mm" for c in CAPAS]

    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_recuadro_del_gris_conserva_el_resultado_del_gris_y_dice_que_capa_se_reporta(self, pagina, dialogos, archivo_epson, epson, capa):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(pagina, capa)
        resultado_del_gris, linea = pagina.recuadro_gris.text().split("\n\n")
        assert resultado_del_gris.startswith("Desfase en la imagen: -2.60 px = -0.110 mm"), "es el resultado del GRIS, no el de la capa elegida"
        assert resultado_del_gris == pagina_mod.texto_recuadro(epson, "gris"), "el resultado del gris es el de siempre, palabra por palabra"
        assert f"la capa {ADJETIVO[capa]}" in linea and "se guarda" in linea and "imprimen" in linea and "Capa reportada" in linea, linea
        for otra in CAPAS:
            if otra != capa:
                assert f"la capa {ADJETIVO[otra]}" not in linea

    @pytest.mark.parametrize("capa", CAPAS)
    def test_solo_el_perfil_de_la_capa_elegida_se_rotula_reportada(self, pagina, dialogos, archivo_epson, capa):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(pagina, capa)
        titulos = [eje.get_title() for eje in pagina._fig_rgb.axes[:3]]
        for c, titulo in zip(CAPAS, titulos):
            nombre = f"Capa {ADJETIVO[c]}"
            if c == capa:
                assert titulo.startswith(f"{nombre} (reportada): en esta cuerda "), titulo
            else:
                assert titulo.startswith(f"{nombre}: en esta cuerda ") and "reportada" not in titulo, titulo
        assert all("reportada" not in eje.get_title() for eje in pagina._fig_gris.axes), "el perfil del gris no se ofrece como reportado"

    @pytest.mark.parametrize("pelicula", ["EPSON009", "braqui_00"])
    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_titulo_de_cada_perfil_conserva_su_numero_y_solo_gana_o_pierde_la_palabra_reportada(self, pagina, dialogos, archivo_epson, archivo_braqui, epson, braqui_00, pelicula, capa):
        """R1-PRU-01: el numero del titulo («en esta cuerda 20.97 px») es el del dibujo: R, G y B se dibujan sobre la fila que da el GRIS (`fila_representativa(resultado, "gris")`). Cambiar el menu solo agrega o quita la palabra
        «(reportada)»: una pagina que rotulara con la fila PROPIA de cada capa cambiaria el numero que el fisico lee (EPSON009: la roja 20.97 px contra 5.24; braqui_00: la azul -10.25 contra -10.41) y el resto de las pruebas no la veia."""
        if pelicula == "EPSON009":
            _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
            resultado = epson
        else:
            _analizada(pagina, dialogos, archivo_braqui, CLICS_PLACA_REAL)
            resultado = braqui_00
        fila = dibujo.fila_representativa(resultado, "gris")
        _elegir(pagina, capa)
        esperados = [dibujo.titulo_del_perfil(resultado, c, fila, reportada=(c == capa)) for c in CAPAS]
        assert [e.get_title() for e in pagina._fig_rgb.axes[:3]] == esperados
        assert [e.get_title().replace(" (reportada)", "") for e in pagina._fig_rgb.axes[:3]] == [dibujo.titulo_del_perfil(resultado, c, fila) for c in CAPAS], \
            "quitada la palabra «(reportada)», el titulo es exactamente el que dibuja `dibujar_perfil`"

    def test_con_la_capa_por_omision_el_perfil_verde_ya_nace_rotulado(self, pagina, dialogos, archivo_epson):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        assert [("(reportada)" in eje.get_title()) for eje in pagina._fig_rgb.axes[:3]] == [False, True, False]

    def test_una_capa_que_no_se_mide_se_muestra_con_su_motivo_y_tambien_se_rotula(self, pagina, dialogos, archivo_braqui, braqui_00):
        assert braqui_00["perfiles"]["R"]["estado"] == "no medible: la mancha esta cortada por el borde de la pelicula", "premisa: la roja de braqui_00 no se mide"
        _analizada(pagina, dialogos, archivo_braqui)
        _elegir(pagina, "R")
        cabeza, cola = _cabeza_y_cola(pagina.recuadro_rgb.text())
        assert cabeza.split("\n") == ["Capa reportada: rojo", "No medible: la mancha esta cortada por el borde de la pelicula"]
        assert cola.split("\n")[0] == "Capa R: No medible: la mancha esta cortada por el borde de la pelicula"
        assert pagina._fig_rgb.axes[0].get_title() == "Capa roja (reportada): no medible"
        assert pagina.recuadro_gris.text().split("\n\n")[1].startswith("Se reporta la capa roja"), "el gris tambien dice cual se reporta, aunque no se pueda medir"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_cambiar_el_menu_no_recalcula_nada(self, pagina, dialogos, archivo_epson, espias_del_motor, capa):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        assert all(n >= 1 for n in espias_del_motor.values()), f"premisa: analizar llama al servicio, al motor y a la medida de cada perfil: {espias_del_motor}"
        antes, resultado = dict(espias_del_motor), pagina._resultado
        for destino in (capa, OTRA_CAPA[capa], capa, "G"):
            _elegir(pagina, destino)
        assert espias_del_motor == antes, f"cambiar la capa volvio a medir: {antes} -> {espias_del_motor}"
        assert pagina.estado == "analizada" and pagina._resultado is resultado, "el resultado es el mismo objeto: no se midio otra vez"

    def test_cambiar_el_menu_conserva_el_zoom_y_los_datos_dibujados(self, pagina, dialogos, archivo_epson):
        """Solo cambian los textos y el rotulo: la figura NO se vuelve a dibujar (si lo hiciera, el zoom que el fisico acaba de hacer en un perfil volveria a la vista completa)."""
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        ejes = list(pagina._fig_rgb.axes)
        artistas = [[id(l) for l in e.lines] + [id(p) for p in e.patches] for e in ejes]
        ejes[0].set_xlim(100, 200)                                  # el fisico hace zoom en el perfil
        limites = [e.get_xlim() for e in ejes]
        titulos_del_gris = [e.get_title() for e in pagina._fig_gris.axes]
        for capa in ("R", "B", "G"):
            _elegir(pagina, capa)
        assert list(pagina._fig_rgb.axes) == ejes, "los mismos ejes"
        assert [[id(l) for l in e.lines] + [id(p) for p in e.patches] for e in ejes] == artistas, "las mismas lineas y bandas (nada se redibujo)"
        assert [e.get_xlim() for e in ejes] == limites and limites[0] == (100, 200), "el zoom se conserva"
        assert [e.get_title() for e in pagina._fig_gris.axes] == titulos_del_gris, "la figura del gris no cambia"

    def test_cambiar_el_menu_conserva_el_tamano_de_letra_de_los_titulos(self, pagina, dialogos, archivo_epson, epson):
        """R1-PRU-03: el rotulo cambia el TEXTO de un titulo ya dibujado y nada mas: `Axes.set_title(texto)` sin tamano devuelve el titulo al de `rcParams` (12 pt en vez de los 8 pt de `dibujar_perfil`), en los tres titulos,
        al dibujar y al cambiar el menu. El tamano esperado se lee del propio dibujo (`dibujar_perfil` sobre una figura aparte), no de un 8 escrito aqui."""
        from matplotlib.figure import Figure
        fila = dibujo.fila_representativa(epson, "gris")
        del_dibujo = []
        for perfil in CAPAS:
            eje = Figure().add_subplot(111)
            dibujo.dibujar_perfil(eje, epson, perfil, fila)
            del_dibujo.append(eje.title.get_fontsize())
        assert len(set(del_dibujo)) == 1 and del_dibujo[0] != Figure().add_subplot(111).title.get_fontsize(), "premisa: el dibujo fija un tamano propio, distinto del de `rcParams`"
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        assert [e.title.get_fontsize() for e in pagina._fig_rgb.axes[:3]] == del_dibujo, "al dibujar"
        for capa in ("R", "B", "G"):
            _elegir(pagina, capa)
            assert [e.title.get_fontsize() for e in pagina._fig_rgb.axes[:3]] == del_dibujo, f"al elegir la capa {capa}"

    def test_cambiar_el_menu_pide_repintar_la_figura_de_las_capas_y_no_la_del_gris(self, pagina, dialogos, archivo_epson, monkeypatch):
        """El rotulo cambia el TEXTO de un titulo ya dibujado: sin pedir el repintado el fisico seguiria viendo el titulo viejo hasta que algo mas repinte el lienzo (y la figura del gris no cambia: no se repinta)."""
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        pedidos = {"capas": 0, "gris": 0}
        monkeypatch.setattr(pagina.lienzo_rgb, "draw_idle", lambda *a, **k: pedidos.__setitem__("capas", pedidos["capas"] + 1))
        monkeypatch.setattr(pagina.lienzo_gris, "draw_idle", lambda *a, **k: pedidos.__setitem__("gris", pedidos["gris"] + 1))
        _elegir(pagina, "R")
        assert pedidos == {"capas": 1, "gris": 0}, f"cambiar la capa debe pedir UN repintado del lienzo de las capas y ninguno del del gris: {pedidos}"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_elegir_la_capa_despues_de_analizar_converge_con_elegirla_antes(self, fabrica, dialogos, archivo_epson, capa):
        """La convergencia de dos caminos se afirma, no se confia: dos paginas con la misma imagen y la misma capa, una que la eligio antes de analizar y otra despues, quedan IGUALES."""
        antes = fabrica()
        _elegir(antes, capa)
        _analizada(antes, dialogos, archivo_epson, CLICS_EPSON009)
        despues = fabrica()
        _analizada(despues, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(despues, capa)
        assert _huella(antes) == _huella(despues)
        assert antes.recuadro_gris.text() == despues.recuadro_gris.text() and antes.recuadro_rgb.text() == despues.recuadro_rgb.text()
        assert [e.get_title() for e in antes._fig_rgb.axes] == [e.get_title() for e in despues._fig_rgb.axes]

    def test_con_el_menu_cambiado_antes_de_analizar_no_hay_nada_que_mostrar_ni_se_rompe_nada(self, pagina, dialogos):
        _elegir(pagina, "B")
        _elegir(pagina, "R")
        assert pagina.capa_reportada == "R" and pagina.recuadro_gris.text() == "" and pagina.recuadro_rgb.text() == "" and not dialogos.llamadas

    def test_un_error_inesperado_al_cambiar_la_capa_se_avisa_con_su_titulo_y_no_escapa(self, pagina, dialogos, archivo_epson, monkeypatch):
        dialogos.criticos_esperados = True
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)

        def revienta(*a, **k):
            raise RuntimeError("fallo de prueba")

        monkeypatch.setattr(pagina, "_rotular_la_capa_reportada", revienta)
        _elegir(pagina, "B")
        critico = dialogos.de("critical")
        assert len(critico) == 1 and critico[0]["titulo"] == "Capa reportada" and "RuntimeError: fallo de prueba" in critico[0]["texto"]

    def test_con_la_linea_no_refinada_ningun_recuadro_interpreta_y_el_aviso_sale_una_vez_en_cada_capa(self, pagina, dialogos, archivo_braqui):
        resultado = svc.analizar_imagen(BRAQUI_00, CLICS_LINEA_ALEJADA)
        aviso = pagina_mod.motivo_para_no_guardar(resultado)
        assert aviso and resultado["perfiles"]["G"]["estado"] == "ok", "premisa: la linea no se refino y la verde se midio (la situacion peligrosa)"
        _analizada(pagina, dialogos, archivo_braqui, CLICS_LINEA_ALEJADA)
        assert not pagina.boton_guardar.isEnabled()
        for capa in CAPAS:
            _elegir(pagina, capa)
            texto = pagina.recuadro_rgb.text()
            assert texto.count(aviso) == 1, f"el aviso debe salir UNA vez con la capa {capa}: {texto!r}"
            assert texto.split("\n")[0] == f"Capa reportada: {COLOR[capa]}"
            for prohibida in ("Cumple", "No cumple", "Tolerancia", "mm =", "La fuente quedó", "antes de la marca", "despues de la marca"):
                assert prohibida not in texto, f"{prohibida!r} en el recuadro de las capas con la capa {capa} y la linea no refinada"
            assert pagina.recuadro_gris.text() == pagina_mod.texto_recuadro(resultado, "gris"), "con la linea sin refinar el gris no dice que 'se guarda' nada: no se puede guardar"

    def test_ninguno_de_los_textos_nuevos_lleva_simbolos_de_correcto_o_incorrecto(self, pagina, dialogos, archivo_braqui, archivo_epson):
        textos = []
        for ruta, clics in ((archivo_epson, CLICS_EPSON009), (archivo_braqui, CLICS_PLACA_REAL)):
            pagina.boton_limpiar.click()
            _analizada(pagina, dialogos, ruta, clics)
            for capa in CAPAS:
                _elegir(pagina, capa)
                textos += [pagina.recuadro_gris.text(), pagina.recuadro_rgb.text(), *[e.get_title() for e in pagina._fig_rgb.axes]]
        textos += [pagina.etiqueta_capa.text(), pagina.selector_capa.toolTip(), *[pagina.selector_capa.itemText(i) for i in range(3)], pagina_mod.linea_de_un_registro_sin_capa("G")]
        assert len(textos) >= 30 and all(_texto_sin_simbolos(t) for t in textos)


# ======================================================================================================== 3. guardar la capa elegida

class TestGuardarGuardaLaCapaElegida:
    def test_sin_tocar_el_menu_guarda_la_capa_por_omision(self, pagina, dialogos, archivo_braqui, bd):
        """El defecto de HEAD: un registro guardado desde la pantalla queda SIN capa y el PDF lo imprime con el gris."""
        _analizada(pagina, dialogos, archivo_braqui)
        pagina.boton_guardar.click()
        assert _consulta(bd, f"SELECT capa_reportada FROM {TABLA}") == [("G",)], "lo guardado dice con que capa se reporta la prueba"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_con_el_escritor_real_guarda_la_capa_elegida_y_la_auditoria_la_nombra(self, pagina, dialogos, archivo_epson, bd, capa):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(pagina, capa)
        pagina.boton_guardar.click()
        assert pagina.estado == "registro" and not dialogos.de("question"), "la capa se midio: no hay nada que confirmar"
        assert _consulta(bd, f"SELECT capa_reportada, estado_r, estado_g, estado_b FROM {TABLA}") == [(capa, "ok", "ok", "ok")]
        auditoria = _auditoria(bd)
        assert [a[0] for a in auditoria] == ["guardar"] and auditoria[0][3].endswith(f"; capa reportada {capa}"), auditoria

    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_llamada_al_servicio_lleva_la_letra_de_pelicula_CAPAS(self, pagina, dialogos, archivo_epson, monkeypatch, capa):
        llamadas, real = [], svc.guardar
        monkeypatch.setattr(svc, "guardar", lambda *a, **k: (llamadas.append((a, k)), real(*a, **k))[1])
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(pagina, capa)
        pagina.boton_guardar.click()
        assert len(llamadas) == 1
        enviada = llamadas[0][1].get("capa_reportada")
        assert enviada == capa and isinstance(enviada, str) and enviada in pel.CAPAS, "la LETRA (no el color) y por palabra clave"

    def test_una_capa_que_no_se_pudo_medir_pide_confirmar_nombrandola_y_solo_se_guarda_si_el_fisico_dice_que_si(self, pagina, dialogos, archivo_braqui, bd):
        _analizada(pagina, dialogos, archivo_braqui)
        _elegir(pagina, "R")
        dialogos.respuesta = QMessageBox.No
        pagina.boton_guardar.click()
        pregunta = dialogos.de("question")[-1]
        assert pregunta["texto"] == ("Antes de guardar:\n- la capa roja, que es la reportada, no se pudo medir: la mancha esta cortada por el borde de la pelicula"
                                     "\n\n¿Guardar de todos modos?")
        assert pregunta["args"][3] == QMessageBox.Yes | QMessageBox.No and pregunta["args"][4] == QMessageBox.No, "con 'No' por omision"
        assert _consulta(bd, f"SELECT COUNT(*) FROM {TABLA}") == [(0,)] and pagina.estado == "analizada", "contestar No no guarda nada"
        dialogos.respuesta = QMessageBox.Yes
        pagina.boton_guardar.click()
        assert len(dialogos.de("question")) == 2, "una sola pregunta por intento"
        assert _consulta(bd, f"SELECT capa_reportada, estado_r, desfase_r_px FROM {TABLA}") == [("R", "no medible: la mancha esta cortada por el borde de la pelicula", None)], \
            "se guarda tal cual (B5-D4): la capa elegida y SU estado, sin numeros"

    @pytest.mark.parametrize("capa", ["G", "B"])
    def test_una_capa_medible_no_pide_nada_aunque_la_roja_no_se_mida(self, pagina, dialogos, archivo_braqui, bd, capa):
        """Con braqui_00 la roja no se mide; guardar con la verde o la azul no pregunta nada: el aviso es de la capa REPORTADA."""
        _analizada(pagina, dialogos, archivo_braqui)
        _elegir(pagina, capa)
        pagina.boton_guardar.click()
        assert not dialogos.de("question") and _consulta(bd, f"SELECT capa_reportada FROM {TABLA}") == [(capa,)]

    def test_el_aviso_es_por_la_capa_elegida_y_no_por_el_gris(self, braqui_00):
        gris_no_medible = _con_estado_del_gris(braqui_00, "no medible: la mancha se sale de la zona marcada")
        assert pagina_mod.motivos_para_confirmar(gris_no_medible, "G") == [], "el gris no se reporta: con la verde medida no hay aviso"
        assert pagina_mod.motivos_para_confirmar(gris_no_medible) == ["el perfil de grises no se pudo medir: la mancha se sale de la zona marcada"], \
            "sin capa (la conducta de siempre) sigue avisando por el gris"
        assert pagina_mod.motivos_para_confirmar(braqui_00, "R") == ["la capa roja, que es la reportada, no se pudo medir: la mancha esta cortada por el borde de la pelicula"], \
            "con el gris medido y la roja no, avisa por la roja"
        assert pagina_mod.motivos_para_confirmar(braqui_00, "G") == [] and pagina_mod.motivos_para_confirmar(braqui_00, "B") == []
        assert pagina_mod.motivos_para_confirmar(braqui_00) == [], "por omision es la conducta de siempre (el gris)"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_aviso_nombra_la_capa_con_su_adjetivo(self, braqui_00, capa):
        sin_medir = {**braqui_00, "perfiles": {**braqui_00["perfiles"], capa: {**braqui_00["perfiles"][capa], "estado": "no medible: porque si"}}}
        assert pagina_mod.motivos_para_confirmar(sin_medir, capa) == [f"la capa {ADJETIVO[capa]}, que es la reportada, no se pudo medir: porque si"]

    def test_el_aviso_de_la_capa_y_el_de_la_resolucion_van_en_la_misma_pregunta(self, braqui_00):
        otra_resolucion = {**braqui_00, "tamano_pixel_mm": None, "dpi": 300.0}
        motivos = pagina_mod.motivos_para_confirmar(otra_resolucion, "R")
        assert len(motivos) == 2 and motivos[0].startswith("la capa roja, que es la reportada") and motivos[1].startswith("no habrá milímetros ni veredicto")

    def test_por_ast_la_llamada_de_la_pagina_a_guardar_pasa_la_capa_reportada(self):
        arbol = ast.parse(PAGINA_PY.read_text(encoding="utf-8"))
        llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "guardar"
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == "svc"]
        assert len(llamadas) == 1, f"la pagina llama a `svc.guardar` en {len(llamadas)} sitios (debe ser uno)"
        claves = {k.arg: k.value for k in llamadas[0].keywords}
        assert "capa_reportada" in claves, "la llamada de la pagina a `svc.guardar` no pasa `capa_reportada`: el registro quedaria sin capa"
        assert not isinstance(claves["capa_reportada"], ast.Constant), "la capa que se guarda sale del menu, no es un literal"


# ===================================================================================================== 4. reabrir un registro guardado

class TestReabrirPoneElMenuEnLaCapaGuardada:
    @pytest.mark.parametrize("capa", CAPAS)
    def test_abrir_un_registro_pone_el_menu_en_su_capa_y_los_recuadros_la_muestran(self, fabrica, dialogos, archivo_epson, capa):
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(p, capa)
        p.boton_guardar.click()
        p.boton_limpiar.click()
        _elegir(p, OTRA_CAPA[capa])                                  # el menu esta en OTRA capa cuando se abre el registro
        dialogos.llamadas.clear()
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p.estado == "registro" and not dialogos.llamadas, "se abre sin avisos: lo recalculado coincide con lo guardado"
        assert p.capa_reportada == capa and p.selector_capa.currentText() == COLOR[capa]
        assert p.recuadro_rgb.text().startswith(f"Capa reportada: {COLOR[capa]}\n")
        assert [("(reportada)" in e.get_title()) for e in p._fig_rgb.axes[:3]] == [c == capa for c in CAPAS]
        assert f"la capa {ADJETIVO[capa]}" in p.recuadro_gris.text()

    @pytest.mark.parametrize("capa", CAPAS)
    def test_abrir_converge_con_analizar_de_nuevo_con_esa_capa(self, fabrica, dialogos, archivo_epson, capa):
        analizada = fabrica()
        _elegir(analizada, capa)
        _analizada(analizada, dialogos, archivo_epson, CLICS_EPSON009)
        analizada.boton_guardar.click()
        abierta = fabrica()
        abierta.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert abierta.recuadro_rgb.text() == analizada.recuadro_rgb.text() and abierta.recuadro_gris.text() == analizada.recuadro_gris.text()
        assert [e.get_title() for e in abierta._fig_rgb.axes] == [e.get_title() for e in analizada._fig_rgb.axes]

    def test_abrir_pone_el_menu_con_las_senales_bloqueadas(self, fabrica, dialogos, archivo_epson, monkeypatch):
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(p, "B")
        p.boton_guardar.click()
        p.boton_limpiar.click()
        llamadas = []
        monkeypatch.setattr(p, "_al_cambiar_capa", lambda indice: llamadas.append(indice))
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p.capa_reportada == "B" and llamadas == [], "abrir un registro no es que el fisico elija: el manejador del menu no corre (se dibuja una vez, en `_mostrar`)"

    def test_limpiar_tampoco_dispara_el_manejador_del_menu(self, fabrica, dialogos, archivo_epson, monkeypatch):
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(p, "B")
        llamadas = []
        monkeypatch.setattr(p, "_al_cambiar_capa", lambda indice: llamadas.append(indice))
        p.boton_limpiar.click()
        assert p.capa_reportada == "G" and llamadas == []

    def test_un_registro_sin_capa_deja_el_menu_en_la_capa_por_omision_y_lo_dice_en_la_etiqueta(self, fabrica, bd):
        """Un registro anterior a B.5, o guardado por la pagina de antes de B.7: el escritor real, sin capa."""
        p = fabrica()
        svc.guardar(USUARIO, CAMBIO, EPSON009, "EPSON009.jpeg", CLICS_EPSON009)
        p.refrescar()
        assert _consulta(bd, f"SELECT capa_reportada FROM {TABLA}") == [(None,)], "premisa: el registro no tiene capa"
        _elegir(p, "B")
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p.estado == "registro" and p.capa_reportada == "G", "el menu vuelve a la capa por omision"
        etiqueta = p.etiqueta_registro.text()
        assert pagina_mod.linea_de_un_registro_sin_capa("G") in etiqueta.split("\n")
        assert "no guardó la capa reportada" in etiqueta and "la capa verde" in etiqueta and "grises" in etiqueta, etiqueta
        assert etiqueta.startswith(f"Registro abierto: cambio de fuente del {CAMBIO}, guardado por {USUARIO}.")

    def test_un_registro_con_capa_no_agrega_esa_linea(self, fabrica, dialogos, archivo_epson):
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(p, "R")
        p.boton_guardar.click()
        p.boton_limpiar.click()
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p.etiqueta_registro.text() == f"Registro abierto: cambio de fuente del {CAMBIO}, guardado por {USUARIO}."

    def test_una_capa_guardada_que_no_es_valida_avisa_y_deja_la_pagina_como_estaba(self, fabrica, dialogos, archivo_epson, bd, monkeypatch):
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        p.boton_guardar.click()
        p.boton_limpiar.click()
        id_registro = _filas(bd)[0][0]
        real = svc.leer
        monkeypatch.setattr(svc, "leer", lambda i: {**real(i), "capa_reportada": "X"})
        antes = _huella(p)
        dialogos.llamadas.clear()
        assert p.abrir_registro(id_registro) is False
        assert dialogos.de("warning")[-1]["texto"] == "No se pudo abrir el registro: la capa reportada guardada no es válida: 'X'"
        assert _huella(p) == antes, "nada cambio: ni el menu ni la imagen ni los recuadros"

    @pytest.mark.parametrize("falla,grave", [(ValueError("fallo de prueba al analizar"), False), (RuntimeError("fallo inesperado al analizar"), True)])
    def test_un_registro_cuyo_analisis_falla_no_mueve_el_menu_ni_deja_la_pagina_a_medias(self, fabrica, dialogos, archivo_epson, monkeypatch, falla, grave):
        """R1-PRU-02: `abrir_registro` lee TODO y calcula ANTES de tocar la pagina («queda como estaba»): si el analisis del registro falla (aviso «No se pudo analizar» o error inesperado) el menu de la capa reportada
        sigue donde el fisico lo dejo. Una `_poner_capa` colocada justo despues de leer la capa del registro (antes de `_calcular`) lo movia a la capa guardada sin que nadie lo tocara y ninguna prueba lo veia: la otra prueba de
        apertura fallida falla antes, en `capa_del_registro`, y las de PI.4 guardan registros sin capa (el menu ya esta en la omision)."""
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(p, "R")
        p.boton_guardar.click()
        p.boton_limpiar.click()
        _elegir(p, "B")                                              # el fisico deja el menu en azul; el registro guardado es de la roja
        antes = _huella(p)
        id_registro = svc.listar()[0]["id"]

        def revienta(*a, **k):
            raise falla

        monkeypatch.setattr(svc, "analizar_imagen", revienta)
        dialogos.criticos_esperados = grave
        dialogos.llamadas.clear()
        assert p.abrir_registro(id_registro) is False
        assert [c["tipo"] for c in dialogos.llamadas] == ["critical" if grave else "warning"], dialogos.llamadas
        assert p.capa_reportada == "B" and p.selector_capa.isEnabled() and p.estado == "vacia", "el menu sigue donde el fisico lo dejo"
        assert _huella(p) == antes, "nada cambio: ni el menu ni la imagen ni los recuadros"

    def test_cambiar_el_menu_sin_guardar_no_cambia_nada_de_lo_guardado(self, pagina, dialogos, archivo_epson, bd):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        pagina.boton_guardar.click()
        filas = _consulta(bd, f"SELECT * FROM {TABLA} ORDER BY id")
        auditoria = _auditoria(bd)
        celdas = [[pagina.tabla_registros.item(0, c).text() for c in range(pagina.tabla_registros.columnCount())]]
        textos = _lo_que_la_pantalla_dice(pagina)
        for capa in ("R", "B", "G", "B"):
            _elegir(pagina, capa)
        assert _consulta(bd, f"SELECT * FROM {TABLA} ORDER BY id") == filas and _auditoria(bd) == auditoria, "lo guardado es lo guardado"
        assert [[pagina.tabla_registros.item(0, c).text() for c in range(pagina.tabla_registros.columnCount())]] == celdas, "ni siquiera la tabla de registros se mueve"
        assert pagina.estado == "registro" and not pagina.boton_guardar.isEnabled(), "elegir otra capa no habilita volver a guardar (para eso, Recalcular)"
        assert _lo_que_la_pantalla_dice(pagina) == textos, "R1-PRU-05: tampoco los textos: la pantalla no puede decir que se reporta otra capa que la guardada"


# ======================================================================================================= 5. la tabla de registros

class TestLaTablaDeRegistrosTieneLaColumnaCapa:
    @pytest.fixture
    def con_cuatro_registros(self, fabrica, bd):
        """Tres registros con capa (R, G, B) y uno SIN capa, escritos con el escritor REAL del servicio sobre EPSON009 (las tres capas se miden)."""
        fechas = {"R": "2026-09-27", "G": "2026-08-27", "B": "2026-07-27", None: "2026-06-27"}
        p = fabrica(tuple(fechas.values()))
        for capa, fecha in fechas.items():
            svc.guardar(USUARIO, fecha, EPSON009, "EPSON009.jpeg", CLICS_EPSON009, capa_reportada=capa)
        p.refrescar()
        return p, fechas

    def test_las_cabeceras_son_cinco_y_la_capa_va_despues_del_resultado(self, pagina):
        assert pagina.tabla_registros.columnCount() == 5
        assert [pagina.tabla_registros.horizontalHeaderItem(i).text() for i in range(5)] == ["Cambio de fuente", "Serie de la fuente", "Guardado por", "Resultado", "Capa"]

    def test_la_columna_capa_dice_el_color_de_cada_registro_y_esta_vacia_si_no_tiene_y_las_otras_siguen_donde_estaban(self, con_cuatro_registros):
        p, fechas = con_cuatro_registros
        t = p.tabla_registros
        assert t.rowCount() == 4
        por_fecha = {t.item(r, 0).data(Qt.UserRole + 1): t.item(r, 4).text() for r in range(4)}
        assert por_fecha == {fechas["R"]: "rojo", fechas["G"]: "verde", fechas["B"]: "azul", fechas[None]: ""}
        for r in range(4):
            fecha = t.item(r, 0).data(Qt.UserRole + 1)
            assert t.item(r, 0).text() == fecha and t.item(r, 1).text() == SERIE_C and t.item(r, 2).text() == USUARIO, "las tres primeras siguen donde estaban"
            assert t.item(r, 0).data(Qt.UserRole) is not None, "la id del registro sigue en la primera celda (X10)"
            assert t.item(r, 3).text() != "", "la cuarta sigue siendo el resultado"

    def test_el_desfase_de_cada_fila_es_el_de_la_capa_de_ese_registro(self, con_cuatro_registros, epson):
        p, fechas = con_cuatro_registros
        t = p.tabla_registros
        prefijo = {"R": "Capa roja: ", "G": "Capa verde: ", "B": "Capa azul: "}
        numeros = {}
        for capa in CAPAS:
            r = motor.resumen(epson, capa)
            fila = next(i for i in range(4) if t.item(i, 0).data(Qt.UserRole + 1) == fechas[capa])
            esperado = f"{prefijo[capa]}{r['desfase_fisico_mm']:.2f} ± {r['U_mm']:.2f} mm (k = 2)"
            assert t.item(fila, 3).text().startswith(esperado), f"{capa}: {t.item(fila, 3).text()!r} no empieza por {esperado!r}"
            assert t.item(fila, 4).text() == COLOR[capa], f"la columna «Capa» de la fila de {capa} dice {t.item(fila, 4).text()!r}: el desfase y la capa de una fila son los del mismo registro"
            numeros[capa] = f"{r['desfase_fisico_mm']:.2f}"
        assert len(set(numeros.values())) == 3, f"compuerta: las tres capas de EPSON009 dan numeros distintos {numeros}"
        fila_sin_capa = next(i for i in range(4) if t.item(i, 0).data(Qt.UserRole + 1) == fechas[None])
        gris = motor.resumen(epson, "gris")
        assert t.item(fila_sin_capa, 3).text().startswith(f"{gris['desfase_fisico_mm']:.2f} ± {gris['U_mm']:.2f} mm (k = 2)"), "sin capa, el resultado es el del gris de siempre, sin prefijo"

    def test_la_celda_del_resultado_es_el_texto_breve_del_servicio_con_el_nombre_de_la_capa(self, con_cuatro_registros):
        """B7-D7 (vetable): la celda «Resultado» conserva el prefijo «Capa verde: » de `texto_breve` (la misma linea que imprimen los PDF); la columna «Capa» repite el color a secas."""
        p, fechas = con_cuatro_registros
        t = p.tabla_registros
        por_id = {r["id"]: r for r in svc.listar()}
        for fila in range(4):
            registro = por_id[t.item(fila, 0).data(Qt.UserRole)]
            assert t.item(fila, 3).text() == svc.texto_breve(registro, con_cambio_de_fuente=False)
            assert t.item(fila, 3).toolTip() == t.item(fila, 3).text()
        # R1-PRU-07: lo que promete el nombre de la prueba: la celda lleva el NOMBRE de la capa de su registro (oraculo escrito aqui, no el del servicio); sin capa, es el gris de siempre, sin prefijo.
        # (Sigue pasando contra HEAD a proposito: es el control de B7-D7, la celda es la de B.6 y B.7 no la cambia.)
        por_fecha = {t.item(r, 0).data(Qt.UserRole + 1): t.item(r, 3).text() for r in range(4)}
        for capa in CAPAS:
            assert por_fecha[fechas[capa]].startswith(f"Capa {ADJETIVO[capa]}: "), por_fecha[fechas[capa]]
        assert not por_fecha[fechas[None]].startswith("Capa "), por_fecha[fechas[None]]

    @pytest.mark.parametrize("ancho", [1500, 1100, 750])
    def test_la_columna_resultado_toma_lo_que_sobra_y_no_deja_un_hueco(self, con_cuatro_registros, ancho):
        """R1-PRU-04, la otra mitad de B7-D10: «Resultado» (la celda larga) toma TODO el ancho que las otras cuatro columnas dejan. Con la columna en su ancho inicial (`Interactive`) la tabla muestra un hueco vacio a la
        derecha y la celda larga se corta sin necesidad (104 px de «Resultado» a 1500 px, cuando su texto pide 657 y sobran 978)."""
        p, _fechas = con_cuatro_registros
        p.resize(ancho, 800)
        p.show()
        QApplication.processEvents()
        t = p.tabla_registros
        otras = sum(t.columnWidth(c) for c in range(t.columnCount()) if c != 3)
        sobra = t.viewport().width() - otras
        assert abs(t.columnWidth(3) - sobra) <= 2, f"«Resultado» mide {t.columnWidth(3)} px y la tabla le deja {sobra} a {ancho} px: queda un hueco vacio"

    @pytest.mark.parametrize("ancho", [1500, 1100, 750])
    def test_la_columna_capa_queda_a_la_vista_a_cualquier_ancho_sin_barra_horizontal(self, con_cuatro_registros, ancho):
        """B7-D10 (vetable): con la celda «Resultado» larga y la columna «Capa» ahora la ultima, «Resultado» toma lo que sobra (su texto completo es la ayuda de la celda) y «Capa» no se va a la derecha de la pantalla."""
        p, _fechas = con_cuatro_registros
        p.resize(ancho, 800)
        p.show()
        QApplication.processEvents()
        t = p.tabla_registros
        assert t.columnCount() == 5, "premisa: la tabla tiene la columna «Capa» (sin ella no habria nada que ver)"
        assert max(len(t.item(r, 3).text()) for r in range(4)) > 60, "premisa: la celda del resultado es larga"
        assert t.horizontalScrollBar().maximum() == 0, f"la tabla se desplaza hacia los lados a {ancho} px: la columna «Capa» queda fuera de la vista"
        assert t.columnViewportPosition(4) + t.columnWidth(4) <= t.viewport().width() and t.columnWidth(4) < 150, "«Capa» se ve entera y no se ensancha de mas"

    def test_al_guardar_desde_la_pagina_la_tabla_trae_la_capa_elegida(self, pagina, dialogos, archivo_epson):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(pagina, "B")
        pagina.boton_guardar.click()
        assert pagina.tabla_registros.rowCount() == 1 and pagina.tabla_registros.item(0, 4).text() == "azul"
        assert pagina.tabla_registros.item(0, 3).text().startswith("Capa azul: ")


# ======================================================================================================== 6. limpiar y recalcular

class TestLimpiarYElMenu:
    def test_limpiar_devuelve_el_menu_a_la_capa_por_omision(self, pagina, dialogos, archivo_epson):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(pagina, "R")
        pagina.boton_limpiar.click()
        assert pagina.capa_reportada == "G" and pagina.selector_capa.currentText() == "verde"

    def test_limpiar_deja_una_pagina_igual_a_una_recien_creada_con_el_menu_cambiado(self, fabrica, dialogos, archivo_epson):
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(p, "B")
        p.boton_guardar.click()
        recien = fabrica()
        assert _huella(p) != _huella(recien), "premisa: el ciclo cambio de verdad el estado"
        p.boton_limpiar.click()
        assert _huella(p) == _huella(recien), "Limpiar = recien creada, tambien en el menu de la capa"

    def test_la_huella_ve_el_menu(self, pagina):
        """Prueba de la prueba: cambiar SOLO el menu cambia la huella (si no, 'Limpiar = recien creada' no vigilaria el menu)."""
        base = _huella(pagina)
        _elegir(pagina, "R")
        assert _huella(pagina) != base
        _elegir(pagina, "G")
        assert _huella(pagina) == base

    def test_recalcular_conserva_la_capa_elegida(self, pagina, dialogos, archivo_epson):
        _analizada(pagina, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(pagina, "R")
        pagina.boton_recalcular.click()
        assert pagina.capa_reportada == "R" and pagina.recuadro_rgb.text() == ""
        _marcar(pagina, CLICS_EPSON009)
        assert pagina.recuadro_rgb.text().startswith("Capa reportada: rojo\n") and pagina._fig_rgb.axes[0].get_title().startswith("Capa roja (reportada)")

    def test_cargar_otra_imagen_conserva_la_capa_elegida(self, fabrica, dialogos, archivo_epson, archivo_braqui):
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(p, "B")
        _cargar(p, dialogos, archivo_braqui)
        assert p.capa_reportada == "B"
        _marcar(p, CLICS_PLACA_REAL)
        assert p.recuadro_rgb.text().startswith("Capa reportada: azul\n")


# ============================================================================================================ 7. por AST

@pytest.fixture(scope="module")
def arbol():
    return ast.parse(PAGINA_PY.read_text(encoding="utf-8"))


class TestLaPaginaPorAst:
    def test_la_pagina_no_escribe_las_tres_capas_a_mano_las_lee_de_pelicula_CAPAS(self, arbol):
        a_mano = _las_tres_capas_a_mano(arbol)           # R1-PRU-06: ve la tupla, pero tambien la lista, el conjunto, el diccionario y la cadena «RGB» (la mutacion `["R", "G", "B"]` pasaba el guardia)
        assert a_mano == [], f"la pagina escribe las tres capas a mano {a_mano}: debe leer `pelicula.CAPAS` (una sola definicion)"
        importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module == "analisisImagenes.pelicula" for a in n.names}
        assert {"CAPAS", "NOMBRE_DE_CAPA", "ADJETIVO_DE_LA_CAPA", "CAPA_POR_OMISION"} <= importados

    def test_capa_por_omision_solo_es_el_valor_inicial_del_menu(self, arbol):
        """DA-85: ningun PDF ni el servicio la leen; en la pagina solo se usa para poner el menu en su valor inicial (al crear/limpiar y al abrir un registro sin capa)."""
        contenedora = {}
        for n in ast.walk(arbol):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for hijo in ast.walk(n):
                    contenedora.setdefault(id(hijo), n.name)
        usos = sorted({contenedora.get(id(n), "(modulo)") for n in ast.walk(arbol) if isinstance(n, ast.Name) and n.id == "CAPA_POR_OMISION" and isinstance(n.ctx, ast.Load)})
        assert usos == ["_restablecer_estado", "abrir_registro"], f"`CAPA_POR_OMISION` se lee en {usos}"

    def test_el_menu_se_lee_solo_donde_corresponde_y_se_bloquea_en_un_solo_sitio(self, arbol):
        """B7-C1 (R1-PROD-01), la clase de error: dos escritores de textos leian el MENU como si fuera la capa reportada, tambien con un registro delante. Hoy el menu (`capa_reportada`) lo leen solo `_capa_que_se_reporta` (la unica
        definicion de la capa que la pantalla reporta), `_al_guardar` (la capa que Guardar guardara) y `abrir_registro` (la linea de la etiqueta de un registro sin capa), y solo `_estado` lo habilita o lo bloquea (una segunda
        definicion de cuando se bloquea dejaria dos fuentes de verdad otra vez)."""
        padres = {id(hijo): n for n in ast.walk(arbol) for hijo in ast.iter_child_nodes(n)}

        def funcion_de(nodo):
            while id(nodo) in padres:
                nodo = padres[id(nodo)]
                if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return nodo.name
            return "(modulo)"

        lecturas = sorted({funcion_de(n) for n in ast.walk(arbol) if isinstance(n, ast.Attribute) and n.attr == "capa_reportada" and isinstance(n.ctx, ast.Load)})
        assert lecturas == ["_al_guardar", "_capa_que_se_reporta", "abrir_registro"], f"el menu (`capa_reportada`) se lee en {lecturas}: lo que la pantalla dice de la capa reportada sale de `_capa_que_se_reporta`"
        habilitan = sorted({funcion_de(n) for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("setEnabled", "setDisabled")
                            and isinstance(n.func.value, ast.Attribute) and n.func.value.attr == "selector_capa"})
        assert habilitan == ["_estado"], f"el menu se habilita o se bloquea en {habilitan}: solo el setter de `_estado` decide cuando"

    def test_el_titulo_de_un_perfil_se_define_una_vez_en_el_modulo_de_dibujo(self, arbol):
        dibujo_ast = ast.parse(DIBUJO_PY.read_text(encoding="utf-8"))
        definidas = [n.name for n in ast.walk(dibujo_ast) if isinstance(n, ast.FunctionDef)]
        assert definidas.count("titulo_del_perfil") == 1
        assert "titulo_del_perfil" not in [n.name for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)], "la pagina la importa, no la define de nuevo"
        assert not [n for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and "(reportada)" in n.value], \
            "el rotulo «reportada» del perfil lo escribe el modulo de dibujo (una sola definicion del titulo)"


class TestElGuardiaDeLasTresCapasATienePruebaPropia:
    """R1-PRU-06: el guardia de «una sola definicion de las capas» tenia una unica forma sintactica (la tupla): una lista o la cadena «RGB» en el menu y en `texto_recuadro_capas` pasaban sin ser vistas. Aqui se
    prueba el guardia con codigo sintetico, en las dos direcciones (lo que debe ver y lo que no)."""

    @pytest.mark.parametrize("codigo,forma", [('x = ("R", "G", "B")', "Tuple"), ('x = ["R", "G", "B"]', "List"), ('x = {"R", "G", "B"}', "Set"), ('x = ("B", "G", "R")', "Tuple"),
                                              ('x = {"R": 1, "G": 2, "B": 3}', "Dict"), ('for c in "RGB":\n    pass', "cadena")])
    def test_ve_cada_forma_de_escribir_las_tres_capas_a_mano(self, codigo, forma):
        assert [f for _linea, f in _las_tres_capas_a_mano(ast.parse(codigo))] == [forma]

    @pytest.mark.parametrize("codigo", ['x = capa == "R"', 'x = ("gris", "R", "G", "B")', 'x = ("R", "G", "B", "barrido")', 'x = ["R", "G"]', 'x = {"R": 1}', 'x = "Capas RGB"', 'x = (1, "G", "B")',
                                        'x = ("R", "R", "B")', 'x = {**otro, "R": 1, "G": 2}'])
    def test_no_ve_lo_que_no_es_una_definicion_de_las_tres_capas(self, codigo):
        assert _las_tres_capas_a_mano(ast.parse(codigo)) == []

    def test_la_pagina_de_hoy_tiene_las_dos_colecciones_con_mas_de_tres_elementos_y_el_guardia_las_deja_pasar(self, arbol):
        """Premisa: la pagina SI escribe dos colecciones con R, G y B mas otros elementos (los ejes y el barrido, de B.1 y B.4); no son la definicion de las capas y el guardia no las cuenta."""
        mixtas = [n.lineno for n in ast.walk(arbol) if isinstance(n, ast.Tuple) and {"R", "G", "B"} <= {getattr(e, "value", None) for e in n.elts} and len(n.elts) > 3]
        assert len(mixtas) == 2 and _las_tres_capas_a_mano(arbol) == []


class TestElTituloDelPerfil:
    @pytest.mark.parametrize("perfil,nombre", [("gris", "Perfil de grises"), ("R", "Capa roja"), ("G", "Capa verde"), ("B", "Capa azul")])
    def test_sin_el_rotulo_es_el_titulo_de_siempre(self, epson, perfil, nombre):
        """`dibujar_perfil` (que usan los PDF de B.6 y la pestana sintetica) no cambia: su titulo es el de siempre y trae el nombre del perfil sin rotulo."""
        fila = dibujo.fila_representativa(epson, "gris")
        titulo = dibujo.titulo_del_perfil(epson, perfil, fila)
        assert titulo.startswith(f"{nombre}: ") and "reportada" not in titulo
        assert dibujo.titulo_del_perfil(epson, perfil, fila, reportada=False) == titulo
        assert dibujo.titulo_del_perfil(epson, perfil, fila, reportada=True) == titulo.replace(f"{nombre}: ", f"{nombre} (reportada): ", 1)

    def test_dibujar_perfil_con_su_valor_por_omision_dibuja_exactamente_ese_titulo(self, epson):
        from matplotlib.figure import Figure
        fila = dibujo.fila_representativa(epson, "gris")
        for perfil in ("gris", "R", "G", "B"):
            eje = Figure().add_subplot(111)
            dibujo.dibujar_perfil(eje, epson, perfil, fila)
            assert eje.get_title() == dibujo.titulo_del_perfil(epson, perfil, fila)

    def test_las_tres_formas_del_titulo_conservan_su_rotulo(self, epson, braqui_00):
        """Medible, no medible y medido contra los puntos: las tres ramas del titulo aceptan el rotulo."""
        no_refinada = svc.analizar_imagen(BRAQUI_00, CLICS_LINEA_ALEJADA)
        casos = [(epson, "G", "Capa verde (reportada): en esta cuerda "), (braqui_00, "R", "Capa roja (reportada): no medible"),
                 (no_refinada, "G", "Capa verde (reportada): medido contra los puntos, no contra la línea")]
        for resultado, perfil, esperado in casos:
            titulo = dibujo.titulo_del_perfil(resultado, perfil, dibujo.fila_representativa(resultado, "gris"), reportada=True)
            assert titulo.startswith(esperado), (perfil, titulo)


# ================================================================ 8. con un registro guardado o abierto la capa que se reporta es la del registro (ronda 1 de revision)

class TestConUnRegistroGuardadoOAbiertoLaCapaEsLaDelRegistro:
    """B7-C1 (R1-PROD-01 y R1-PRU-05): con un registro guardado o abierto, Guardar queda deshabilitado pero el menu seguia vivo, y al moverlo la pantalla afirmaba lo contrario de lo guardado e impreso («Se reporta la capa
    azul ...: es la que se guarda con el registro y la que imprimen los PDF», «Capa reportada: azul», el perfil azul «(reportada)») mientras la BD, la columna «Capa» y el PDF seguian con la capa guardada. Ahora la capa que
    la pantalla reporta con un registro es la que GUARDO el registro (`_capa_que_se_reporta`), el menu queda fijo en ella (como Guardar) y no vuelve a ser una eleccion hasta que la pagina deja de mostrar el registro."""

    @staticmethod
    def _en_registro(fabrica, dialogos, archivo_epson, capa, como):
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        _elegir(p, capa)
        p.boton_guardar.click()
        if como == "abierto":
            p.boton_limpiar.click()
            p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p.estado == "registro" and p.capa_reportada == capa
        return p

    @pytest.mark.parametrize("como", ["guardado", "abierto"])
    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_menu_queda_fijo_en_la_capa_del_registro(self, fabrica, dialogos, archivo_epson, capa, como):
        p = self._en_registro(fabrica, dialogos, archivo_epson, capa, como)
        assert not p.selector_capa.isEnabled(), "con un registro guardado o abierto la capa no es una eleccion: es la que guardo el registro"
        assert p.selector_capa.currentText() == COLOR[capa] and not p.boton_guardar.isEnabled()
        assert "Recalcular" in p.selector_capa.toolTip(), "el menu fijo dice como se reporta otra capa (la ayuda lo explica)"

    @pytest.mark.parametrize("como", ["guardado", "abierto"])
    @pytest.mark.parametrize("capa", CAPAS)
    def test_mover_el_menu_no_cambia_lo_que_la_pantalla_dice_de_la_capa_reportada(self, fabrica, dialogos, archivo_epson, capa, como):
        p = self._en_registro(fabrica, dialogos, archivo_epson, capa, como)
        antes = _lo_que_la_pantalla_dice(p)
        for otra in CAPAS:
            if otra == capa:
                continue
            _elegir(p, otra)                    # por codigo: la pagina deshabilitada no se puede mover con el raton, pero ningun camino debe hacer que la pantalla contradiga lo guardado
            gris, rgb, titulos = _lo_que_la_pantalla_dice(p)
            assert (gris, rgb, titulos) == antes
            assert f"la capa {ADJETIVO[otra]}" not in gris and not rgb.startswith(f"Capa reportada: {COLOR[otra]}"), "la pantalla dice que se reporta la capa del menu y no la guardada"
            assert [("(reportada)" in t) for t in titulos] == [c == capa for c in CAPAS], "el perfil rotulado «reportada» es el de la capa guardada"
        assert _capa_que_dice_la_pantalla(p) == capa

    @pytest.mark.parametrize("como", ["guardado", "abierto"])
    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_capa_que_dice_la_pantalla_es_la_que_imprime_el_pdf_y_la_de_la_tabla(self, fabrica, dialogos, archivo_epson, capa, como):
        """La convergencia se afirma: pantalla, PDF y tabla de registros dicen la MISMA capa, tambien con el menu movido por codigo."""
        p = self._en_registro(fabrica, dialogos, archivo_epson, capa, como)
        for otra in [c for c in CAPAS if c != capa]:          # el menu termina en una capa DISTINTA de la guardada
            _elegir(p, otra)
        assert p.capa_reportada != capa
        assert _capa_que_dice_la_pantalla(p) == _capa_que_imprime_el_pdf(CAMBIO) == capa
        assert p.tabla_registros.item(0, 4).text() == COLOR[capa]

    @pytest.mark.parametrize("como", ["guardado", "abierto"])
    @pytest.mark.parametrize("salida", ["recalcular", "limpiar", "otra_imagen"])
    def test_el_menu_vuelve_a_ser_una_eleccion_cuando_la_pagina_deja_de_mostrar_el_registro(self, fabrica, dialogos, archivo_epson, archivo_braqui, como, salida):
        p = self._en_registro(fabrica, dialogos, archivo_epson, "R", como)
        assert not p.selector_capa.isEnabled()
        if salida == "recalcular":
            p.boton_recalcular.click()
        elif salida == "limpiar":
            p.boton_limpiar.click()
        else:
            _cargar(p, dialogos, archivo_braqui)
        assert p.estado != "registro" and p.selector_capa.isEnabled(), "sin registro delante, el menu es de nuevo la eleccion del fisico"
        _elegir(p, "B")
        assert p.capa_reportada == "B"

    def test_un_analisis_nuevo_deja_el_menu_disponible(self, fabrica, dialogos, archivo_epson):
        p = self._en_registro(fabrica, dialogos, archivo_epson, "G", "guardado")
        p.boton_recalcular.click()
        _marcar(p, CLICS_EPSON009)
        assert p.estado == "analizada" and p.selector_capa.isEnabled()
        _elegir(p, "R")
        assert p.recuadro_rgb.text().startswith("Capa reportada: rojo\n"), "con un analisis sin guardar, la capa que se reporta es la del menu"

    def test_si_abrir_falla_al_dibujar_el_menu_no_queda_fijo(self, fabrica, dialogos, archivo_epson, monkeypatch):
        """`abrir_registro` marca el estado «registro» antes de dibujar (lo que se dice de la capa sale del registro); si dibujar falla, la pagina queda «fallida», sin resultado y con el menu disponible."""
        p = fabrica()
        _analizada(p, dialogos, archivo_epson, CLICS_EPSON009)
        p.boton_guardar.click()
        p.boton_limpiar.click()

        def revienta(*a, **k):
            raise RuntimeError("fallo de prueba al dibujar")

        monkeypatch.setattr(p, "_mostrar", revienta)
        dialogos.criticos_esperados = True
        assert p.abrir_registro(svc.listar()[0]["id"]) is False
        assert p.estado == "fallida" and p._resultado is None and p.selector_capa.isEnabled() and not p.boton_guardar.isEnabled()

    def test_el_menu_deshabilitado_conserva_su_ayuda_y_su_rotulo(self, fabrica, dialogos, archivo_epson):
        p = self._en_registro(fabrica, dialogos, archivo_epson, "B", "guardado")
        assert p.etiqueta_capa.text() == "Capa reportada:" and p.etiqueta_capa.buddy() is p.selector_capa and p.selector_capa.toolTip()


class TestUnRegistroSinCapaNoDiceQueSeReportaNinguna:
    """B7-C1 (R1-PROD-02): un registro anterior a B.5 (o guardado sin capa) no reporta ninguna: el PDF lo imprime con el gris, como antes. El menu queda en la capa por omision (el plan) y la etiqueta lo dice, pero el
    recuadro del gris afirmaba «Se reporta la capa verde ...: es la que se guarda con el registro y la que imprimen los PDF», lo contrario de la etiqueta y del PDF."""

    @pytest.fixture
    def abierto_sin_capa(self, fabrica, bd):
        p = fabrica()
        svc.guardar(USUARIO, CAMBIO, EPSON009, "EPSON009.jpeg", CLICS_EPSON009)       # el escritor real, sin capa (como los de antes de B.5)
        p.refrescar()
        assert _consulta(bd, f"SELECT capa_reportada FROM {TABLA}") == [(None,)], "premisa: el registro no tiene capa"
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p.estado == "registro"
        return p

    def test_los_recuadros_y_los_titulos_son_los_de_siempre_sin_afirmar_ninguna_capa(self, abierto_sin_capa):
        p = abierto_sin_capa
        resultado = p._resultado
        assert p.recuadro_gris.text() == pagina_mod.texto_recuadro(resultado, "gris"), "el gris, como antes de B.7: sin la linea de la capa reportada"
        assert p.recuadro_rgb.text() == pagina_mod.texto_recuadro_capas(resultado), "las capas, como antes de B.7: sin la cabeza «Capa reportada»"
        assert [e.get_title() for e in p._fig_rgb.axes[:3]] == [dibujo.titulo_del_perfil(resultado, c, dibujo.fila_representativa(resultado, "gris")) for c in CAPAS]
        assert _capa_que_dice_la_pantalla(p) is None

    def test_lo_que_dice_la_pantalla_es_lo_que_imprime_el_pdf(self, abierto_sin_capa):
        assert _capa_que_dice_la_pantalla(abierto_sin_capa) is None and _capa_que_imprime_el_pdf(CAMBIO) is None
        assert abierto_sin_capa.tabla_registros.item(0, 4).text() == ""

    def test_el_menu_queda_en_la_omision_fijo_y_moverlo_no_cambia_nada(self, abierto_sin_capa):
        p = abierto_sin_capa
        assert p.capa_reportada == pel.CAPA_POR_OMISION and not p.selector_capa.isEnabled()
        antes = _lo_que_la_pantalla_dice(p)
        for capa in CAPAS:
            _elegir(p, capa)
            assert _lo_que_la_pantalla_dice(p) == antes

    def test_la_etiqueta_sigue_diciendo_que_el_registro_no_tiene_capa(self, abierto_sin_capa):
        etiqueta = abierto_sin_capa.etiqueta_registro.text()
        assert pagina_mod.linea_de_un_registro_sin_capa(pel.CAPA_POR_OMISION) in etiqueta.split("\n")
