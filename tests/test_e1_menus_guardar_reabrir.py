"""E.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-83 a DA-86): los dos menus de la ventana del analisis mensual («Capa reportada» y «Piso»), el boton «Pelicula virgen...», guardar y reabrir, Limpiar y
Recalcular, la robustez y la memoria de la ventana, y lo que la ventana NO hace (por AST). Lo que la ventana dibuja esta en `test_e1_ventana_placa_mensual.py` y la regla de D.1b (una capa no medible no
se ofrece) en `test_e1_capa_no_medible.py`.

LO QUE SE GARANTIZA, todo POR EL CAMINO DEL USUARIO (botones y menus reales, clics reales, la sintetica de PF.0, el escritor REAL del servicio y una BD temporal; nunca una BD de referencia):
  1. «CAPA REPORTADA» (DA-85). Rojo, verde y azul con la letra como dato; arranca en `CAPA_POR_OMISION` (la constante, no una letra escrita a mano); la rueda sin foco no la cambia; CAMBIARLA NO
     RECALCULA NI REDIBUJA (espias sobre el motor y el servicio: cero llamadas; los dibujos no cambian) y solo mueve lo que depende de ella (la fila «se guarda», el rotulo «(reportada)», la nota, la linea del
     piso), mientras los perfiles y la tabla de la pestana 1 siguen siendo los del GRIS; elegirla antes de analizar converge con elegirla despues; `Guardar` le pasa al servicio LA ELEGIDA (R, G y B) y
     se guarda esa capa con los numeros del motor.
  2. «PISO». Tres modos con su dato; el punto marcado solo con un sexto clic y la virgen solo con una referencia valida (con su archivo y su fecha en el texto); CAMBIARLO SI RECALCULA (con las mismas marcas) y
     en el modo virgen no hay region del piso en la pelicula y la linea dice la comparacion; `refrescar` (y `showEvent`) lee la referencia otra vez y, si el modo elegido ya no esta disponible, vuelve al de omision
     y mide de nuevo; un archivo de referencia danado se dice y no se usa.
  3. «PELICULA VIRGEN...». Elegir el escaneo, medirlo, el cuadro con la zona dibujada, su valor por capa, cada comprobacion con su cifra y su resultado en palabras, la orientacion declarada, y «Guardar como
     referencia» solo si es valida (si ya habia una pregunta con «No» por omision y la anterior se archiva); la ventana escribe el archivo junto a la base y la fila de auditoria; una virgen rechazada no se guarda.
  4. GUARDAR Y REABRIR. Guardar llama al servicio con los clics SIN refinar, todos los parametros de fabrica (la base incluida), la capa y el modo y deja lo mismo que el servicio llamado directo; una pregunta de reemplazo con «No»
     por omision; el control anulado o un rechazo del servicio se dicen tal cual y la ventana queda como estaba. Abrir un control con analisis guardado carga la imagen y los puntos, vuelve a medir con LOS
     PARAMETROS, EL PISO Y LA COPIA DE LA VIRGEN GUARDADOS (nunca los de hoy ni la referencia vigente) y compara con lo guardado (DD3: una diferencia se dice); la capa y el piso quedan fijos (B7-C1); lo que
     la ventana muestra al reabrir es lo que mostraba al guardar.
  5. LIMPIAR deja la ventana igual a una recien creada (huella del arbol de widgets, corolario 3); RECALCULAR conserva la imagen y las elecciones de los menus y borra puntos, sexto clic y resultado.
  6. ROBUSTEZ. Ningun manejador deja escapar una excepcion (AST y por fallos inyectados), ningun cuadro se abre con el cursor de espera, una pagina entera del escaner (6600 x 5100) se abre, se dibuja y se
     analiza sin retener la pelicula leida.
  7. POR AST. La ventana no tiene SQL ni `cv2` ni `pyplot`, no importa la `motivo_para_no_guardar` de braqui ni define otra, lee `CAPA_POR_OMISION` y el modo por omision solo como valor inicial de sus menus,
     no escribe las tres capas a mano, define el titulo de un perfil UNA vez y llama a `svc.guardar` con la capa y el modo.

Trampa 2 (todo `QMessageBox` y todo cuadro se parcha: la fixture `dialogos`; el cuadro de la virgen no se ejecuta de verdad: lo ejecuta una sustitucion que HACE lo que haria el fisico dentro de el), Trampa 9
(cada ventana y cada cuadro se cierran con la receta completa), Trampa 10 (ningun `lru_cache`).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import dataclasses
import tracemalloc
from pathlib import Path

import numpy as np
import pytest
from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QComboBox, QMessageBox

import _corpus
import _placa_mensual_sintetica as gen
from _e1_ayudas import (ADJETIVO, CAPAS, COLOR, DIBUJO_PY, FECHA_DE_PRUEBA, USUARIO, VENTANA_PY, HoyFijo, _cursor_limpio, analizada, app, archivo_placa, cargar, cerrar, clic, con_gid, dialogos,  # noqa: F401
                        elegir_capa, elegir_piso, escaneo_virgen, fabrica, guardada, huella, marcar, otro_escaneo_virgen, parametros, pel, pm, por_gid, recorrer, resultado_directo, svc,  # noqa: F401
                        texto_de_la_tabla, ventana, ventana_mod)
from test_d1_guardado_placa_mensual import _auditoria, _consulta, _control, _sql, bd, clics, placa, plantilla  # noqa: F401  (fixtures y ayudas de D.1)

CLICS_EPSON027 = [(206, 150), (2552, 154), (1381, 1337), (2536, 2508), (181, 2487)]     # los clics de la pagina entera del escaner (los de ML0 mas su desplazamiento, C.1)
from _e1_ayudas import con_la_base_de_pixel  # noqa: F401  (fixture)


# OD.1 (DA-87): la netOD es la base por omision del analisis y el rojo de la sintetica esta recortado en ella (la capa roja ya no se mide ni se guarda). Las pruebas de la
# ventana de E.1 prueban el flujo (marcar, medir, guardar, reabrir, la regla de D.1b) con las TRES capas medibles, asi que fijan la base de VALOR DE PIXEL en todo el
# archivo; la ventana en netOD (el menu del piso, el cuadro de la virgen, los perfiles dibujados en la base) la prueba `test_od1_densidad_optica.py`.
@pytest.fixture(scope="module", autouse=True)
def _base_de_pixel(con_la_base_de_pixel):
    yield


TABLA = "analisis_placa_mensual"


# ------------------------------------------------------------------------------------------------------ fixtures y ayudas

def _carpeta(bd):
    """La carpeta de la base: donde la ventana guarda la referencia de la pelicula virgen."""
    return os.path.dirname(bd)


def _guardar_referencia(bd, escaneo, usuario=USUARIO):
    pel().guardar_referencia_virgen(escaneo.referencia, _carpeta(bd), escaneo.datos, usuario)


@pytest.fixture
def espias(monkeypatch):
    """Cuenta las llamadas a lo que MIDE, GUARDA o LEE la referencia: el motor, el barrido, la medida de un perfil, el servicio y `leer_referencia_virgen`."""
    llamadas = {"analizar": [], "barrido": [], "medir_perfil": [], "guardar": [], "recalcular": [], "referencia": []}

    def envolver(modulo, nombre, clave):
        real = getattr(modulo, nombre)

        def f(*a, **k):
            llamadas[clave].append((a, k))
            return real(*a, **k)
        monkeypatch.setattr(modulo, nombre, f)
    envolver(pm(), "analizar", "analizar")
    envolver(pm(), "barrido", "barrido")
    envolver(pm(), "medir_perfil", "medir_perfil")
    envolver(svc(), "guardar", "guardar")
    envolver(svc(), "recalcular", "recalcular")
    envolver(pel(), "leer_referencia_virgen", "referencia")
    return llamadas


def _valores(datos, limite=200):
    """Los valores de una linea como una tupla comparable: redondeados y con lo no finito (NaN: fuera de la pelicula) cambiado por una marca, porque NaN no es igual a si mismo."""
    return tuple(np.round(np.nan_to_num(np.asarray(datos, dtype=float), nan=-999.0, posinf=-998.0, neginf=-997.0), 6)[:limite].tolist())


def _estado_de_los_dibujos(v):
    """Lo que las cinco figuras dibujan, como valores comparables: por eje, cuantos artistas de cada clase y los datos de cada linea (no solo cuantas hay)."""
    foto = []
    for lienzo in (v.lienzo_imagen, v.lienzo_gris, v.lienzo_capas, v.lienzo_perfiles, v.lienzo_barridos, v.lienzo_cuadratura):
        for ax in lienzo.figure.axes:
            lineas = tuple((l.get_gid(), _valores(l.get_xdata()), _valores(l.get_ydata())) for l in ax.get_lines())
            foto.append((len(ax.images), len(ax.patches), len(ax.collections), lineas))
    return foto


def _huella_del_analisis(v):
    """La huella (sha256) de la pelicula virgen con que se midio el analisis que la ventana tiene a la vista, o None si se midio sin una (el piso automatico y el punto marcado no la usan)."""
    referencia = v._resultado.piso.referencia
    return None if referencia is None else referencia.procedencia["sha256"]


def _datos_del_perfil(v):
    """Los datos de los dos perfiles del gris de la pestana 1 (las lineas de cada eje, con su valor)."""
    return [[(l.get_gid(), _valores(l.get_ydata())) for l in ax.get_lines()] for ax in v._fig_gris.axes]


def _mostrado(v):
    """Todo lo que la ventana dice y dibuja de un analisis, para comparar dos ventanas (tablas, rotulos, recuadros, titulos de los perfiles)."""
    return {"desfases": texto_de_la_tabla(v.tabla_desfases), "perfiles": texto_de_la_tabla(v.tabla_perfiles), "barridos": texto_de_la_tabla(v.tabla_barridos),
            "cuadratura": texto_de_la_tabla(v.tabla_cuadratura), "nota": v.nota_pestana1.text(), "piso": v.etiqueta_piso.text(), "linea": v.linea_regla.text(),
            "titulos": [a.get_title() for a in v._fig_perfiles.axes], "capas": [a.get_title() for a in v._fig_capas.axes], "marcas": v.etiqueta_marcas.text()}


# ================================================================================================= 1. el menu «Capa reportada»

class TestElMenuCapaReportada:
    def test_ofrece_rojo_verde_y_azul_con_la_letra_como_dato(self, ventana):
        combo = ventana.selector_capa
        assert [combo.itemText(i) for i in range(combo.count())] == ["rojo", "verde", "azul"] and [combo.itemData(i) for i in range(combo.count())] == ["R", "G", "B"] and not combo.isEditable()

    @pytest.mark.parametrize("otra", ["R", "B"])
    def test_arranca_en_lo_que_diga_la_constante_y_no_en_una_letra_escrita_a_mano(self, fabrica, monkeypatch, otra):
        monkeypatch.setattr(pel(), "CAPA_POR_OMISION", otra)
        v = fabrica()
        assert v.capa_reportada == otra and v.selector_capa.currentText() == COLOR[otra]

    @pytest.mark.parametrize("inicial", CAPAS)
    def test_la_rueda_del_raton_no_cambia_la_capa_si_el_menu_no_tiene_el_foco(self, ventana, inicial):
        elegir_capa(ventana, inicial)
        assert not ventana.selector_capa.hasFocus()
        rueda = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), 0, Qt.Vertical, Qt.NoButton, Qt.NoModifier)
        QApplication.sendEvent(ventana.selector_capa, rueda)
        assert ventana.capa_reportada == inicial and not rueda.isAccepted()

    def test_una_tecla_del_teclado_si_cambia_la_capa(self, ventana):
        assert ventana.capa_reportada == "G"
        QTest.keyClick(ventana.selector_capa, Qt.Key_Down)
        assert ventana.capa_reportada == "B"

    def test_con_el_foco_la_rueda_si_cambia_la_capa(self, ventana, monkeypatch):
        """La proteccion es solo contra la rueda que PASA por encima: un menu que tiene el foco la atiende como cualquier otro."""
        monkeypatch.setattr(ventana_mod()._SelectorSinRueda, "hasFocus", lambda self: True)
        elegir_capa(ventana, "G")
        rueda = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), 0, Qt.Vertical, Qt.NoButton, Qt.NoModifier)
        QApplication.sendEvent(ventana.selector_capa, rueda)
        assert ventana.capa_reportada == "B"

    def test_ningun_menu_nuestro_toma_el_foco_con_la_rueda_su_politica_es_strongfocus(self, ventana, escaneo_virgen, app):
        """E1-REV1-PRU-03 (ronda 1 de la revision). Las pruebas de la rueda mandan un `wheelEvent` con `QApplication.sendEvent` a una ventana que NUNCA se muestra: `hasFocus()` es siempre falso y la politica
        de foco del menu no se ejercitaba (quitar la linea que la fija dejaba verdes las tres suites). El mecanismo de Qt: un `QComboBox` nace con `WheelFocus` y, con un paso REAL de la rueda sobre el menu
        cerrado, Qt le da el foco ANTES de entregarle `wheelEvent`; `hasFocus()` ya seria verdadero y la proteccion de `_SelectorSinRueda` no protegeria nada. Con `StrongFocus` (clic o tabulador, nunca
        la rueda) el menu solo tiene el foco si el fisico se lo dio. Eso no se puede provocar con eventos sinteticos (no son espontaneos): se afirma la politica, en CADA menu que la ventana crea."""
        assert QComboBox().focusPolicy() == Qt.WheelFocus, "premisa de Qt: un menu cerrado nace aceptando el foco con la rueda"
        cuadro = ventana_mod().DialogoPeliculaVirgen(escaneo_virgen.referencia, escaneo_virgen.datos, None, None)
        try:
            menus = {"Capa reportada": ventana.selector_capa, "Piso": ventana.selector_piso, "orientacion de la pelicula virgen": cuadro.selector_orientacion}
            for nombre, menu in menus.items():
                assert menu.focusPolicy() == Qt.StrongFocus, f"el menu «{nombre}» acepta el foco con la rueda: {menu.focusPolicy()}"
            todos = [w for w in recorrer(ventana) if isinstance(w, QComboBox)] + [w for w in recorrer(cuadro) if isinstance(w, QComboBox)]
            assert len(todos) == 3 and all(type(w) is ventana_mod()._SelectorSinRueda for w in todos), "compuerta: el censo de los widgets encuentra los tres menus, todos de la clase protegida"
        finally:
            cerrar(cuadro)

    def test_tiene_una_sola_conexion_su_ayuda_y_su_rotulo_asociado(self, ventana):
        assert ventana.selector_capa.receivers(ventana.selector_capa.currentIndexChanged) == 1 and ventana.selector_capa.toolTip()
        assert ventana.etiqueta_capa.buddy() is ventana.selector_capa and ventana.etiqueta_piso_menu.buddy() is ventana.selector_piso

    def test_cambiar_el_menu_no_recalcula_ni_redibuja_nada(self, fabrica, dialogos, archivo_placa, clics, espias):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        llamadas = {k: len(x) for k, x in espias.items()}
        antes = _estado_de_los_dibujos(v)
        for capa in ("R", "B", "G", "R"):
            elegir_capa(v, capa)
        assert {k: len(x) for k, x in espias.items()} == llamadas, "cambiar la capa no mide (analizar, barrido, medir_perfil) ni guarda ni lee la referencia"
        assert _estado_de_los_dibujos(v) == antes, "y no redibuja los datos: las cinco figuras tienen las mismas lineas"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_fila_se_guarda_el_rotulo_reportada_la_nota_y_la_linea_del_piso_siguen_a_la_capa_elegida(self, fabrica, dialogos, archivo_placa, clics, capa):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_capa(v, capa)
        filas = texto_de_la_tabla(v.tabla_perfiles)
        assert [f[11] for f in filas] == ["se guarda" if f[0] == f"Capa {ADJETIVO[capa]}" else "" for f in filas]
        titulos = [a.get_title() for a in v._fig_perfiles.axes]
        assert [("(reportada)" in t) for t in titulos] == [t.startswith(f"Capa {ADJETIVO[capa]}") for t in titulos] and sum("(reportada)" in t for t in titulos) == 2
        assert v.nota_pestana1.text() == f"Estos son los desfases del perfil de grises. Lo que se guarda y se imprime es lo de la capa {ADJETIVO[capa]}, que se ve en la pestaña 3."
        assert v.etiqueta_piso.text().startswith("Base de la medida: ") and f"Piso (capa {ADJETIVO[capa]}): " in v.etiqueta_piso.text()      # OD.1: la linea empieza por la base

    def test_los_perfiles_y_la_tabla_de_la_pestana_1_son_los_del_gris_y_no_cambian_con_el_menu(self, fabrica, dialogos, archivo_placa, clics):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        tabla, perfiles, titulos = texto_de_la_tabla(v.tabla_desfases), _datos_del_perfil(v), [a.get_title() for a in v._fig_gris.axes]
        for capa in ("R", "B"):
            elegir_capa(v, capa)
            assert texto_de_la_tabla(v.tabla_desfases) == tabla and _datos_del_perfil(v) == perfiles and [a.get_title() for a in v._fig_gris.axes] == titulos
            assert all(t.startswith("Gris") and "reportada" not in t for t in titulos)

    @pytest.mark.parametrize("capa", ["R", "B"])
    def test_elegir_la_capa_antes_de_analizar_converge_con_elegirla_despues(self, fabrica, dialogos, archivo_placa, clics, capa):
        despues = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_capa(despues, capa)
        antes = fabrica()
        cargar(antes, dialogos, archivo_placa)
        elegir_capa(antes, capa)
        marcar(antes, clics)
        assert antes.estado == "analizada" and antes.capa_reportada == capa and _mostrado(antes) == _mostrado(despues)

    @pytest.mark.parametrize("capa", CAPAS)
    def test_guardar_pasa_la_capa_elegida_y_se_guarda_esa_capa_con_los_numeros_del_motor(self, fabrica, dialogos, archivo_placa, clics, placa, espias, capa):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_capa(v, capa)
        v.boton_guardar.click()
        (args, _k), = espias["guardar"]
        assert args[6] == capa, "la LETRA de la capa elegida (de `pelicula.CAPAS`) es lo que viaja al servicio"
        registro = svc().leer(v.ref)
        resultado, _b, _m = resultado_directo(placa.datos, clics)
        valores = pm().valores_medidos(resultado, capa)
        assert registro["capa"] == capa and {k: registro[k] for k in valores} == valores

    def test_sin_tocar_el_menu_se_guarda_la_capa_por_omision(self, fabrica, dialogos, archivo_placa, clics, espias):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        v.boton_guardar.click()
        assert espias["guardar"][0][0][6] == pel().CAPA_POR_OMISION and svc().leer(v.ref)["capa"] == "G"

    def test_reabrir_pone_el_menu_en_la_capa_guardada_y_lo_deja_fijo(self, fabrica, dialogos, archivo_placa, clics):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_capa(v, "B")
        v.boton_guardar.click()
        otra = fabrica(ref=v.ref_de_prueba)
        assert otra.estado == "registro" and otra.capa_reportada == "B" and otra.selector_capa.currentText() == "azul" and not otra.selector_capa.isEnabled() and not otra.selector_piso.isEnabled()

    def test_con_un_registro_la_capa_que_dice_la_pantalla_es_la_guardada_aunque_se_mueva_el_menu_por_codigo(self, fabrica, dialogos, archivo_placa, clics):
        """B7-C1: el menu queda fijo; si el codigo lo mueve, la pantalla no contradice lo guardado (la capa sale del registro)."""
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        antes = _mostrado(v)
        v.selector_capa.setCurrentIndex(CAPAS.index("R"))
        assert _mostrado(v) == antes and "capa verde" in v.nota_pestana1.text()
        assert sum("(reportada)" in a.get_title() for a in v._fig_perfiles.axes) == 2 and v._fig_perfiles.axes[2].get_title().startswith("Capa verde (reportada)")

    def test_un_registro_no_se_puede_cambiar_de_capa_pero_recalcular_lo_libera(self, fabrica, dialogos, archivo_placa, clics):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        assert not v.selector_capa.isEnabled() and not v.selector_piso.isEnabled() and not v.boton_guardar.isEnabled()
        v.boton_recalcular.click()
        assert v.selector_capa.isEnabled() and v.selector_piso.isEnabled() and v.capa_reportada == "G"


# ================================================================================================= 2. el menu «Piso»

class TestElMenuDelPiso:
    def test_ofrece_los_tres_modos_con_su_dato_y_solo_el_automatico_al_empezar(self, ventana):
        combo = ventana.selector_piso
        assert [combo.itemData(i) for i in range(3)] == list(pel().MODOS_DEL_PISO) == ["automatico", "punto_manual", "virgen"]
        assert [combo.itemText(i) for i in range(3)] == ["Automático (esquinas)", "Punto marcado (sexto clic)", "Película virgen (no hay referencia)"]
        assert [combo.model().item(i).isEnabled() for i in range(3)] == [True, False, False]

    def test_la_rueda_del_raton_no_cambia_el_piso_si_el_menu_no_tiene_el_foco(self, fabrica, bd, escaneo_virgen):
        """Cambiar el piso vuelve a medir y cambia los numeros: pasar la rueda por la ventana no puede hacerlo (la virgen esta disponible: sin la proteccion la rueda saltaria a ella)."""
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        assert v.selector_piso.model().item(2).isEnabled() and v.modo_del_piso == "virgen" and not v.selector_piso.hasFocus()       # OD.1: con una referencia vigente el menu arranca en la virgen
        v._poner_modo("automatico")                    # el fisico tiene elegido el automatico (la virgen sigue disponible: sin la proteccion la rueda saltaria a ella)
        rueda = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), 0, Qt.Vertical, Qt.NoButton, Qt.NoModifier)
        QApplication.sendEvent(v.selector_piso, rueda)
        assert v.modo_del_piso == "automatico" and not rueda.isAccepted()

    def test_con_una_referencia_valida_la_virgen_se_ofrece_con_su_archivo_y_su_fecha(self, fabrica, bd, escaneo_virgen):
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        assert v.selector_piso.model().item(2).isEnabled()
        assert v.selector_piso.itemText(2) == f"Película virgen «virgen_lote.tif» ({escaneo_virgen.fecha})"

    def test_refrescar_lee_la_referencia_otra_vez_y_mostrar_la_ventana_tambien(self, ventana, bd, escaneo_virgen, espias):
        assert not ventana.selector_piso.model().item(2).isEnabled()
        _guardar_referencia(bd, escaneo_virgen)
        ventana.refrescar()
        assert ventana.selector_piso.model().item(2).isEnabled()
        llamadas = len(espias["referencia"])
        ventana.show()
        assert len(espias["referencia"]) == llamadas + 1, "`showEvent` vuelve a leer la referencia: otro equipo pudo guardar una mientras la ventana estaba abierta"

    def test_cambiar_el_piso_si_recalcula_con_las_mismas_marcas_y_el_modo_elegido(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, espias):
        _guardar_referencia(bd, escaneo_virgen)
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        assert len(espias["analizar"]) == 1
        primera = espias["analizar"][0][1]
        assert primera["modo_piso"] == "virgen" and primera["referencia_virgen"].procedencia["sha256"] == escaneo_virgen.referencia.procedencia["sha256"] and primera["punto_manual"] is None, \
            "OD.1: con una referencia vigente el menu arranca en la virgen y el primer analisis la usa"
        elegir_piso(v, "automatico")
        assert len(espias["analizar"]) == 2 and v.estado == "analizada"
        (args, kwargs) = espias["analizar"][1]
        assert kwargs["modo_piso"] == "automatico" and kwargs["referencia_virgen"] is None and kwargs["punto_manual"] is None, "el modo automatico no recibe la referencia aunque haya una"
        assert [m.clic for m in args[1]] == [m.clic for m in v.marcas], "con las mismas marcas ya hechas"
        assert v._resultado.piso.modo == "automatico"
        elegir_piso(v, "virgen")
        assert len(espias["analizar"]) == 3 and v.estado == "analizada"
        assert espias["analizar"][2][1]["modo_piso"] == "virgen" and espias["analizar"][2][1]["referencia_virgen"] is not None and v._resultado.piso.modo == "virgen"

    def test_en_el_modo_virgen_no_hay_region_en_la_pelicula_y_la_linea_dice_la_comparacion(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, placa):
        _guardar_referencia(bd, escaneo_virgen)
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_piso(v, "virgen")
        assert not con_gid(v.eje_imagen, "piso:") and not any(con_gid(ax, "piso:") for ax in v._fig_capas.axes[:3]), "ninguna region del piso en la pelicula"
        resultado, _b, _m = resultado_directo(placa.datos, clics, "virgen", None, escaneo_virgen.referencia)
        texto = pel().texto_breve_del_piso(resultado.piso, "G") + " " + pel().texto_de_la_comparacion(resultado.piso) + "".join(" " + a for a in resultado.piso.avisos)
        texto = ventana_mod().dibujo.texto_de_la_base(resultado.base) + " " + texto          # OD.1: la linea del piso empieza por la base del analisis
        assert v.etiqueta_piso.text() == texto, f"\n{v.etiqueta_piso.text()!r}\n{texto!r}"
        assert "película virgen «virgen_lote.tif»" in v.etiqueta_piso.text() and "Comparación" in v.etiqueta_piso.text() and pel().texto_de_la_comparacion(resultado.piso)

    def test_la_linea_del_piso_dice_los_avisos_del_piso(self, fabrica, dialogos, tmp_path, bd, escaneo_virgen):
        """Una pelicula JPEG medida con una virgen en TIFF: el piso lo AVISA (la compresion del JPEG cambia unos niveles) y la linea del piso lo dice, junto a la comparacion. Con la pelicula PNG de arriba
        no hay ningun aviso y la prueba de la linea no los distingue."""
        _guardar_referencia(bd, escaneo_virgen)
        jpeg = gen.generar("jpeg", variante="A", seed=1)
        ruta = tmp_path / "placa.jpg"
        ruta.write_bytes(jpeg.datos)
        v = analizada(fabrica(), dialogos, str(ruta), [tuple(map(float, c)) for c in jpeg.verdad.clics_del_cuaderno()])
        elegir_piso(v, "virgen")
        piso = v._resultado.piso
        assert v.estado == "analizada" and piso.estado == "ok" and len(piso.avisos) == 1 and piso.avisos[0].startswith("La película es un JPEG y la virgen un TIFF"), piso.avisos
        assert piso.avisos[0] in v.etiqueta_piso.text() and "Comparación" in v.etiqueta_piso.text()

    def test_elegir_el_modo_virgen_antes_de_los_cinco_puntos_no_mide_y_se_usa_al_completarlos(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, espias):
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        elegir_piso(v, "virgen")
        assert not espias["analizar"] and v.modo_del_piso == "virgen"
        marcar(v, clics)
        assert len(espias["analizar"]) == 1 and espias["analizar"][0][1]["modo_piso"] == "virgen" and v._resultado.piso.modo == "virgen"

    def test_si_la_referencia_desaparece_el_menu_vuelve_al_de_omision_y_mide_de_nuevo(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, espias):
        _guardar_referencia(bd, escaneo_virgen)
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_piso(v, "virgen")
        medidas = len(espias["analizar"])
        os.remove(os.path.join(_carpeta(bd), pel().ARCHIVO_REFERENCIA_VIRGEN))
        v.refrescar()
        assert v.modo_del_piso == "automatico" and len(espias["analizar"]) == medidas + 1 and espias["analizar"][-1][1]["modo_piso"] == "automatico" and v._resultado.piso.modo == "automatico"
        assert not v.selector_piso.model().item(2).isEnabled()

    @pytest.mark.parametrize("como", ["refrescar", "el boton Pelicula virgen..."])
    def test_si_la_referencia_vigente_cambia_con_un_analisis_virgen_en_pantalla_se_mide_de_nuevo_y_lo_guardado_es_lo_que_se_vio(self, como, fabrica, dialogos, archivo_placa, clics, tmp_path, bd,
                                                                                                                                  escaneo_virgen, otro_escaneo_virgen, espias, monkeypatch):
        """E1-PROD-01 (ronda 1 de la revision). Con el analisis en pantalla en el modo «virgen» (medido con la referencia A), otro equipo guarda una referencia B (o el fisico la cambia con «Pelicula virgen...»).
        El menu «Piso» pasa a nombrar la B y «Guardar» guarda con ella, pero la ventana solo volvia a medir si el modo YA NO estaba disponible: la pantalla seguia mostrando el analisis hecho con la A y
        sin avisar, y lo guardado (con la B) diferia de lo que el fisico vio (en la sintetica, el piso de la capa roja 105 contra 106). Ahora el analisis que la ventana tiene a la vista se mide otra vez
        con la referencia vigente, por los dos caminos que la cambian, y lo guardado es exactamente lo que se mostraba."""
        monkeypatch.setattr(ventana_mod(), "date", HoyFijo)               # por el boton, la ventana escribe la fecha de HOY: se fija (E1-R2-PRU-04)
        _guardar_referencia(bd, escaneo_virgen)
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_piso(v, "virgen")
        sha_a, sha_b = escaneo_virgen.referencia.procedencia["sha256"], otro_escaneo_virgen.referencia.procedencia["sha256"]
        assert sha_a != sha_b and _huella_del_analisis(v) == sha_a and v.modo_del_piso == "virgen", "premisa: el analisis de la pantalla se midio con la A"
        medidas = len(espias["analizar"])
        if como == "refrescar":
            _guardar_referencia(bd, otro_escaneo_virgen)                       # otro equipo la guarda; la ventana se vuelve a mostrar (`showEvent` llama a `refrescar`)
            v.refrescar()
        else:
            _elegir_la_virgen(v, dialogos, tmp_path, otro_escaneo_virgen)      # el fisico la cambia: «¿Reemplazarla?» -> Si
            assert [c["cursor"] for c in dialogos.llamadas] == [None] * len(dialogos.llamadas), "ningun cuadro se abre con el cursor de espera, tampoco el aviso que sigue a medir de nuevo"
        assert len(espias["analizar"]) == medidas + 1, "se midio de nuevo, una sola vez"
        assert espias["analizar"][-1][1]["modo_piso"] == "virgen" and espias["analizar"][-1][1]["referencia_virgen"].procedencia["sha256"] == sha_b
        assert v.estado == "analizada" and v.modo_del_piso == "virgen" and _huella_del_analisis(v) == sha_b, "la pantalla muestra el analisis hecho con la referencia vigente"
        assert f"huella {sha_b[:8]}" in v.etiqueta_piso.text() and sha_a[:8] not in v.etiqueta_piso.text(), "y la linea del piso lo dice"
        assert v.selector_piso.itemText(2) == f"Película virgen «{otro_escaneo_virgen.nombre}» ({otro_escaneo_virgen.fecha})"
        v.boton_guardar.click()
        registro = svc().leer(v.ref)
        assert registro["piso"]["referencia_virgen"]["procedencia"]["sha256"] == sha_b
        assert svc().diferencias(registro, v._resultado) == [], "lo guardado es exactamente lo que la pantalla mostraba"

    def test_si_la_referencia_no_cambia_ni_refrescar_ni_mostrar_la_ventana_vuelven_a_medir(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, espias):
        """El control de E1-PROD-01: medir cuesta segundos; una referencia que sigue siendo la misma no se vuelve a medir, ni al refrescar ni al mostrar la ventana (`showEvent`) ni al volver a leerla del disco."""
        _guardar_referencia(bd, escaneo_virgen)
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_piso(v, "virgen")
        medidas, lecturas = len(espias["analizar"]), len(espias["referencia"])
        v.refrescar()
        v.refrescar()
        v.show()
        v.hide()
        v.show()
        assert len(espias["referencia"]) > lecturas, "compuerta: la referencia SE volvio a leer del disco"
        assert len(espias["analizar"]) == medidas and v.estado == "analizada" and _huella_del_analisis(v) == escaneo_virgen.referencia.procedencia["sha256"]

    def test_la_misma_pelicula_virgen_con_otra_orientacion_declarada_tambien_se_mide_de_nuevo(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, espias):
        """La referencia vigente es la copia entera que guarda el archivo, con su procedencia (la copia viaja dentro de cada analisis, DA-81): cambiar la orientacion declarada de la MISMA pelicula (la huella
        no cambia) cambia lo que se guardaria con el analisis, asi que se mide de nuevo. Comparar solo la huella dejaria la pantalla con la copia vieja."""
        _guardar_referencia(bd, escaneo_virgen)
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_piso(v, "virgen")
        medidas = len(espias["analizar"])
        r = escaneo_virgen.referencia
        pel().guardar_referencia_virgen(dataclasses.replace(r, procedencia={**r.procedencia, "orientacion_declarada": "girada"}), _carpeta(bd), None, USUARIO)
        v.refrescar()
        assert len(espias["analizar"]) == medidas + 1 and v._resultado.piso.referencia.procedencia["orientacion_declarada"] == "girada"
        v.boton_guardar.click()
        assert svc().leer(v.ref)["piso"]["referencia_virgen"]["procedencia"]["orientacion_declarada"] == "girada"

    def test_un_cambio_de_la_referencia_no_vuelve_a_medir_un_analisis_hecho_con_otro_piso(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, otro_escaneo_virgen, espias):
        """El analisis automatico (o con el punto marcado) no usa la referencia: que otro equipo guarde una no lo cambia, no se mide de nuevo."""
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        elegir_piso(v, "automatico")                   # OD.1: con una referencia el menu arranca en la virgen; el fisico elige las esquinas
        analizada(v, dialogos, archivo_placa, clics)
        medidas = len(espias["analizar"])
        _guardar_referencia(bd, otro_escaneo_virgen)
        v.refrescar()
        assert len(espias["analizar"]) == medidas and v.modo_del_piso == "automatico" and v._resultado.piso.referencia is None
        assert v.selector_piso.itemText(2) == f"Película virgen «{otro_escaneo_virgen.nombre}» ({otro_escaneo_virgen.fecha})", "el menu si nombra la referencia nueva"

    def test_con_un_registro_un_cambio_de_la_referencia_vigente_no_vuelve_a_medir_ni_cambia_lo_que_dice(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, otro_escaneo_virgen, espias):
        """Un registro se muestra con SU copia (la guardada manda, DA-81) y «Guardar» esta apagado: aunque la referencia vigente sea otra, no se mide de nuevo y la pantalla no cambia."""
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        elegir_piso(v, "virgen")
        marcar(v, clics)
        v.boton_guardar.click()
        assert v.estado == "registro"
        medidas, antes = len(espias["analizar"]), _mostrado(v)
        _guardar_referencia(bd, otro_escaneo_virgen)
        v.refrescar()
        assert v.estado == "registro" and len(espias["analizar"]) == medidas and _mostrado(v) == antes and not v.boton_guardar.isEnabled()
        assert _huella_del_analisis(v) == escaneo_virgen.referencia.procedencia["sha256"]

    def test_un_archivo_de_referencia_danado_se_dice_y_no_se_usa(self, fabrica, bd):
        Path(_carpeta(bd), pel().ARCHIVO_REFERENCIA_VIRGEN).write_text("{esto no es json", encoding="utf-8")
        v = fabrica()
        assert not v.selector_piso.model().item(2).isEnabled() and v.selector_piso.itemText(2) == "Película virgen (no hay referencia)"
        assert "dañado" in v.etiqueta_piso.text() and not v.etiqueta_piso.isHidden()

    def test_con_un_registro_abierto_el_modo_queda_fijo_aunque_la_referencia_vigente_desaparezca(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, espias):
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        elegir_piso(v, "virgen")
        marcar(v, clics)
        v.boton_guardar.click()
        assert v.estado == "registro"
        medidas = len(espias["analizar"])
        os.remove(os.path.join(_carpeta(bd), pel().ARCHIVO_REFERENCIA_VIRGEN))
        v.refrescar()
        assert v.estado == "registro" and v.modo_del_piso == "virgen" and len(espias["analizar"]) == medidas, "un registro no se vuelve a medir porque cambie la referencia vigente: manda su copia"

    def test_con_un_registro_en_el_modo_virgen_el_menu_nombra_la_copia_que_uso_y_no_la_referencia_vigente(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, otro_escaneo_virgen):
        """E1-R2-PROD-05 (ronda 2 de la revision). Con un analisis guardado a la vista el menu «Piso» queda fijo (B7-C1) y el analisis se midio con SU copia de la pelicula virgen (la guardada manda, DA-81): la linea
        del piso y la etiqueta del registro hablan de esa copia, asi que el renglon seleccionado del menu tambien. Antes nombraba la referencia VIGENTE: otra («virgen_otro_lote.tif») si otro equipo guardo una
        nueva, o «Película virgen (no hay referencia)» si la vigente desaparecio, contradiciendo a la linea de al lado."""
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        elegir_piso(v, "virgen")
        marcar(v, clics)
        v.boton_guardar.click()
        assert v.estado == "registro" and v.modo_del_piso == "virgen"
        propio = f"Película virgen «virgen_lote.tif» ({escaneo_virgen.fecha})"
        assert v.selector_piso.itemText(2) == propio
        _guardar_referencia(bd, otro_escaneo_virgen)                           # (a) otro equipo guarda una referencia nueva
        w = fabrica(ref=v.ref_de_prueba)                                       # un control con analisis guardado se abre solo
        assert w.estado == "registro" and w.modo_del_piso == "virgen" and not w.selector_piso.isEnabled() and "virgen_lote.tif" in w.etiqueta_piso.text()
        for ventana_ in (w, v):                                                # tampoco al refrescar (`showEvent`), ni en la ventana que abrio el registro ni en la que lo guardo
            ventana_.refrescar()
            assert ventana_.selector_piso.itemText(2) == propio and ventana_.modo_del_piso == "virgen"
        os.remove(os.path.join(_carpeta(bd), pel().ARCHIVO_REFERENCIA_VIRGEN))      # (b) la referencia vigente desaparece
        x = fabrica(ref=v.ref_de_prueba)
        assert x.estado == "registro" and x.selector_piso.itemText(2) == propio and "virgen_lote.tif" in x.etiqueta_piso.text()
        x.refrescar()
        assert x.selector_piso.itemText(2) == propio
        x.boton_recalcular.click()                                             # (c) Recalcular libera el menu: sin un analisis guardado el renglon dice lo que hay HOY (nada) y el modo vuelve al de omision
        assert x.selector_piso.itemText(2) == "Película virgen (no hay referencia)" and x.modo_del_piso == "automatico"

    @pytest.mark.parametrize("error", [PermissionError(13, "Permission denied", "piso_pelicula_virgen.json"), OSError(5, "Input/output error"),
                                       FileNotFoundError(2, "No such file or directory", "piso_pelicula_virgen.json")], ids=["permisos", "entrada_salida", "desaparece_en_la_red"])
    def test_una_lectura_de_la_referencia_que_falla_con_un_error_del_sistema_se_dice_y_no_se_usa(self, fabrica, bd, escaneo_virgen, monkeypatch, error):
        """E1-R2-PRU-01 (ronda 2 de la revision). `leer_referencia_virgen` solo convierte en `ValueError` lo que esta mal DENTRO del archivo; si el archivo no se puede abrir (permisos, la red caida, un archivo que
        desaparece entre `isfile` y `open`) deja pasar el `OSError`, y `refrescar` (que llama `showEvent`) lo atrapa, lo dice y no usa la referencia. Sin ese `except` el error escaparia del evento de mostrar la ventana."""
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        assert v.selector_piso.model().item(2).isEnabled(), "premisa: con la referencia legible el menu la ofrece"

        def mal(carpeta):
            raise error
        monkeypatch.setattr(pel(), "leer_referencia_virgen", mal)
        escapo = None
        try:
            v.refrescar()
        except Exception as inesperado:                                       # noqa: BLE001
            escapo = inesperado
        assert escapo is None, f"`refrescar` deja escapar {type(escapo).__name__}: {escapo}"
        assert str(error) in v.etiqueta_piso.text() and not v.etiqueta_piso.isHidden(), "el error se dice en la linea del piso"
        assert not v.selector_piso.model().item(2).isEnabled() and v.selector_piso.itemText(2) == "Película virgen (no hay referencia)", "la referencia que no se pudo leer no se usa"


# ================================================================================================= 3. «Pelicula virgen...»

def _elegir_la_virgen(v, dialogos, tmp_path, escaneo, nombre=None):
    """El fisico pulsa «Pelicula virgen...» y elige ese escaneo (escrito con ese nombre en una carpeta temporal)."""
    ruta = tmp_path / (nombre or escaneo.nombre)
    ruta.write_bytes(escaneo.datos)
    dialogos.ruta = str(ruta)
    v.boton_virgen.click()
    return ruta


class TestPeliculaVirgen:
    def test_el_cuadro_dice_el_valor_por_capa_cada_comprobacion_con_palabras_y_de_donde_salio(self, escaneo_virgen, app):
        r = escaneo_virgen.referencia
        cuadro = ventana_mod().DialogoPeliculaVirgen(r, escaneo_virgen.datos, None, None)
        try:
            assert cuadro.windowTitle() == "Película virgen" and cuadro.boton_guardar.isEnabled()
            valores = texto_de_la_tabla(cuadro.tabla_valores)
            assert [f[0] for f in valores] == ["Capa roja", "Capa verde", "Capa azul", "Gris"] and [f[1] for f in valores] == [f"{r.valor(c):.1f}" for c in ("R", "G", "B", "gris")]      # OD.1: el valor del piso es la media
            pruebas = texto_de_la_tabla(cuadro.tabla_pruebas)
            assert len(pruebas) == len(r.pruebas) == 11 and all(f[1] in ("pasa", "aviso", "rechazo") and f[2] for f in pruebas)      # OD.1: una mas, «C3 fondo: no se ve fondo del escaner; no se juzga»
            assert [f[1] for f in pruebas] == ["pasa"] * 11 and "virgen_lote.tif" in cuadro.procedencia.text() and "huella" in cuadro.procedencia.text() and cuadro.resumen.text() == r.descripcion()
            assert [cuadro.selector_orientacion.itemText(i) for i in range(2)] == ["misma que la película irradiada", "girada"] and cuadro.orientacion_declarada() == "misma que la película irradiada"
            assert por_gid(cuadro.eje, "virgen:zona"), "la zona que se midio se ve dibujada sobre el escaneo"
        finally:
            cerrar(cuadro)

    def test_un_cuadro_para_una_referencia_que_ya_declara_su_orientacion_la_muestra_elegida_y_en_su_procedencia(self, escaneo_virgen, app):
        r = dataclasses.replace(escaneo_virgen.referencia, procedencia={**escaneo_virgen.referencia.procedencia, "orientacion_declarada": "girada"})
        cuadro = ventana_mod().DialogoPeliculaVirgen(r, escaneo_virgen.datos, None, None)
        try:
            assert cuadro.orientacion_declarada() == "girada" and "orientación declarada: girada" in cuadro.procedencia.text()
            assert cuadro.referencia_final().procedencia["orientacion_declarada"] == "girada"
        finally:
            cerrar(cuadro)

    def test_un_escaneo_que_ya_no_se_puede_leer_deja_el_cuadro_con_sus_tablas_y_sin_imagen(self, escaneo_virgen, app):
        cuadro = ventana_mod().DialogoPeliculaVirgen(escaneo_virgen.referencia, b"esto no es una imagen", None, None)
        try:
            assert cuadro.tabla_valores.rowCount() == 4 and cuadro.tabla_pruebas.rowCount() == 11 and not cuadro.eje.images and not por_gid(cuadro.eje, "virgen:zona")
        finally:
            cerrar(cuadro)

    def test_una_pelicula_virgen_rechazada_no_se_puede_guardar_y_el_cuadro_dice_por_que(self, placa, app):
        rechazada = pel().piso_de_pelicula_virgen(placa.datos, parametros(), "irradiada.png", fecha_calculo="2026-10-21")
        assert rechazada.estado.startswith("no válida")
        cuadro = ventana_mod().DialogoPeliculaVirgen(rechazada, placa.datos, None, None)
        try:
            assert not cuadro.boton_guardar.isEnabled()
            resultados = {f[0]: f[1] for f in texto_de_la_tabla(cuadro.tabla_pruebas)}
            assert resultados["rango"] == "rechazo" and resultados["C3 recorte"] == "aviso" and resultados["C5 uniformidad"] == "aviso"      # OD.1: el recorte y la uniformidad avisan; el rango rechaza
            cuadro._al_guardar()
            assert not cuadro.guardar_solicitado, "ni llamando al manejador por codigo se pide guardar una referencia que no es valida"
        finally:
            cerrar(cuadro)

    def test_guardar_como_referencia_escribe_el_archivo_junto_a_la_base_y_la_fila_de_auditoria(self, ventana, dialogos, tmp_path, bd, escaneo_virgen):
        _elegir_la_virgen(ventana, dialogos, tmp_path, escaneo_virgen)
        assert dialogos.orden() == ["cuadro_de_la_virgen", "information"] and [c["cursor"] for c in dialogos.llamadas] == [None, None], "ningun cuadro se abre con el cursor de espera"
        referencia = pel().leer_referencia_virgen(_carpeta(bd))
        assert referencia is not None and referencia.procedencia["sha256"] == escaneo_virgen.referencia.procedencia["sha256"] and referencia.procedencia["archivo"] == "virgen_lote.tif"
        assert referencia.procedencia["orientacion_declarada"] == "misma que la película irradiada"
        sha = escaneo_virgen.referencia.procedencia["sha256"]
        escaneos = list((Path(_carpeta(bd)) / pel().CARPETA_ESCANEOS_VIRGEN).iterdir())
        assert len(escaneos) == 1 and escaneos[0].name.startswith(sha) and escaneos[0].read_bytes() == escaneo_virgen.datos, "el escaneo se copia con su huella como nombre"
        auditoria = _consulta(bd, "SELECT accion, usuario, ref, detalle FROM audit_log WHERE tabla = 'piso_pelicula_virgen'")
        assert len(auditoria) == 1 and auditoria[0][:3] == ("guardar", USUARIO, sha[:8]) and "virgen_lote.tif" in auditoria[0][3] and "orientación misma que la película irradiada" in auditoria[0][3]
        assert auditoria[0][3] == "referencia de la película virgen «virgen_lote.tif»; TIFF; 8 bits; sin fecha de escaneo; orientación misma que la película irradiada", \
            "E1-R2-PROD-04: el escaneo no trae fecha (la sintetica es un TIFF sin etiqueta de fecha) y la fila lo dice con palabras, no «escaneada el sin fecha»"
        assert "Película virgen guardada como referencia: «virgen_lote.tif»" in dialogos.de("information")[0]["texto"]

    def test_la_fila_de_auditoria_dice_la_fecha_del_escaneo_si_el_archivo_la_trae(self, ventana, dialogos, tmp_path, bd, escaneo_virgen):
        """E1-R2-PROD-04: con la fecha del escaneo (la que trae el archivo) la fila dice «escaneada el <fecha>»; la sintetica no la trae, asi que el cuadro recibe una referencia con ella."""
        def con_fecha(cuadro):
            cuadro.referencia = dataclasses.replace(cuadro.referencia, procedencia={**cuadro.referencia.procedencia, "fecha_escaneo": "2026-10-13"})
            cuadro.boton_guardar.click()
        dialogos.accion_virgen = con_fecha
        _elegir_la_virgen(ventana, dialogos, tmp_path, escaneo_virgen)
        assert _consulta(bd, "SELECT detalle FROM audit_log WHERE tabla = 'piso_pelicula_virgen'") == [
            ("referencia de la película virgen «virgen_lote.tif»; TIFF; 8 bits; escaneada el 2026-10-13; orientación misma que la película irradiada",)]

    def test_despues_de_guardar_la_virgen_el_menu_del_piso_la_ofrece(self, ventana, dialogos, tmp_path, escaneo_virgen, monkeypatch):
        """La fecha la escribe la ventana (la de HOY, cuando se mide la pelicula): el reloj de la ventana se fija para que la prueba no dependa del dia en que corre (E1-R2-PRU-04)."""
        monkeypatch.setattr(ventana_mod(), "date", HoyFijo)
        assert not ventana.selector_piso.model().item(2).isEnabled()
        _elegir_la_virgen(ventana, dialogos, tmp_path, escaneo_virgen)
        assert ventana.selector_piso.model().item(2).isEnabled() and ventana.selector_piso.itemText(2) == f"Película virgen «virgen_lote.tif» ({FECHA_DE_PRUEBA})"

    def test_la_orientacion_declarada_en_el_cuadro_se_guarda_con_la_referencia_y_en_la_auditoria(self, ventana, dialogos, tmp_path, bd, escaneo_virgen):
        def girada(cuadro):
            cuadro.selector_orientacion.setCurrentIndex(1)
            cuadro.boton_guardar.click()
        dialogos.accion_virgen = girada
        _elegir_la_virgen(ventana, dialogos, tmp_path, escaneo_virgen)
        assert pel().leer_referencia_virgen(_carpeta(bd)).procedencia["orientacion_declarada"] == "girada"
        assert "orientación girada" in _consulta(bd, "SELECT detalle FROM audit_log WHERE tabla = 'piso_pelicula_virgen'")[0][0]

    def test_una_virgen_rechazada_no_escribe_nada_ni_audita(self, ventana, dialogos, tmp_path, bd, placa):
        ruta = tmp_path / "irradiada.png"
        ruta.write_bytes(placa.datos)
        dialogos.ruta = str(ruta)
        ventana.boton_virgen.click()
        assert dialogos.orden() == ["cuadro_de_la_virgen"] and not dialogos.cuadros_de_la_virgen[0].boton_guardar.isEnabled()
        assert pel().leer_referencia_virgen(_carpeta(bd)) is None and not _consulta(bd, "SELECT 1 FROM audit_log WHERE tabla = 'piso_pelicula_virgen'")

    def test_cancelar_el_cuadro_de_archivo_o_un_archivo_ilegible_no_abre_el_cuadro(self, ventana, dialogos, tmp_path, bd):
        dialogos.ruta = ""
        ventana.boton_virgen.click()
        assert not dialogos.llamadas
        dialogos.ruta = str(tmp_path / "no_existe.tif")
        ventana.boton_virgen.click()
        assert dialogos.orden() == ["warning"] and "No se pudo leer el archivo" in dialogos.de("warning")[0]["texto"] and pel().leer_referencia_virgen(_carpeta(bd)) is None

    def test_con_una_referencia_vigente_guardar_pregunta_con_no_por_omision_y_si_se_dice_que_no_no_cambia_nada(self, ventana, dialogos, tmp_path, bd, escaneo_virgen, otro_escaneo_virgen):
        _guardar_referencia(bd, escaneo_virgen)
        ventana.refrescar()
        dialogos.respuesta = QMessageBox.No
        _elegir_la_virgen(ventana, dialogos, tmp_path, otro_escaneo_virgen)
        pregunta = dialogos.de("question")[0]
        assert pregunta["por_omision"] == QMessageBox.No and pregunta["botones"] == QMessageBox.Yes | QMessageBox.No and "virgen_lote.tif" in pregunta["texto"] and "se archiva, no se borra" in pregunta["texto"]
        assert not dialogos.de("information") and pel().leer_referencia_virgen(_carpeta(bd)).procedencia["archivo"] == "virgen_lote.tif"
        assert not _consulta(bd, "SELECT 1 FROM audit_log WHERE tabla = 'piso_pelicula_virgen'")

    def test_si_se_dice_que_si_la_anterior_se_archiva_y_la_auditoria_dice_reemplazo(self, ventana, dialogos, tmp_path, bd, escaneo_virgen, otro_escaneo_virgen):
        _guardar_referencia(bd, escaneo_virgen)
        ventana.refrescar()
        dialogos.respuesta = QMessageBox.Yes
        _elegir_la_virgen(ventana, dialogos, tmp_path, otro_escaneo_virgen)
        assert pel().leer_referencia_virgen(_carpeta(bd)).procedencia["archivo"] == "virgen_otro_lote.tif"
        assert len(list((Path(_carpeta(bd)) / pel().CARPETA_REFERENCIAS_VIRGEN_ANTERIORES).iterdir())) == 1, "la anterior se archiva y nada se borra"
        assert [f[0] for f in _consulta(bd, "SELECT accion FROM audit_log WHERE tabla = 'piso_pelicula_virgen'")] == ["reemplazo"]

    def test_si_el_guardado_falla_se_dice_y_no_se_audita(self, ventana, dialogos, tmp_path, bd, escaneo_virgen, monkeypatch):
        def falla(*a, **k):
            raise OSError("disco lleno")
        monkeypatch.setattr(pel(), "guardar_referencia_virgen", falla)
        _elegir_la_virgen(ventana, dialogos, tmp_path, escaneo_virgen)
        assert "No se guardó la película virgen: disco lleno" in dialogos.de("warning")[0]["texto"] and not dialogos.de("information")
        assert not _consulta(bd, "SELECT 1 FROM audit_log WHERE tabla = 'piso_pelicula_virgen'")


# ================================================================================================= 4. guardar y reabrir

def _sin_ruido(registro):
    """Un registro leido sin lo que cambia de un guardado a otro (los ids, el control y el instante)."""
    return {k: v for k, v in registro.items() if k not in ("id", "ref", "fecha_registro")}


class TestGuardar:
    def test_guarda_con_los_clics_sin_refinar_los_40_parametros_la_capa_y_el_modo(self, fabrica, dialogos, archivo_placa, clics, placa, espias):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        v.boton_guardar.click()
        (args, kwargs), = espias["guardar"]
        assert args[0] == v.ref_de_prueba and args[1] == USUARIO and args[2] == placa.datos and args[3] == "placa.png"
        assert args[4] == [m.clic for m in v.marcas] and all(m.estado == "refinada" and m.punto != m.clic for m in v.marcas), "los clics SIN refinar: el servicio los refina el mismo"
        assert args[5] == parametros() and len(args[5]) == len(pm().VALORES_DE_LA_GEOMETRIA) == 42 and args[6] == "G" and args[7] == "automatico" and kwargs == {"punto_manual": None, "referencia_virgen": None}

    def test_guardar_llamado_por_codigo_sin_un_analisis_de_esta_sesion_no_hace_nada(self, fabrica, dialogos, archivo_placa, clics, espias):
        v = fabrica()
        v._al_guardar()                                           # ventana vacia
        assert not dialogos.llamadas and not espias["guardar"]
        cargar(v, dialogos, archivo_placa)
        antes = len(dialogos.llamadas)
        v._al_guardar()                                           # con la imagen y sin analisis
        assert len(dialogos.llamadas) == antes and not espias["guardar"]
        g = guardada(fabrica(), dialogos, archivo_placa, clics)   # ya guardada: Guardar ya hizo lo suyo
        antes = (len(dialogos.llamadas), len(espias["guardar"]))
        g._al_guardar()
        assert (len(dialogos.llamadas), len(espias["guardar"])) == antes and antes[1] == 1

    def test_deja_lo_mismo_que_el_servicio_llamado_directo_con_los_mismos_clics(self, fabrica, dialogos, archivo_placa, clics, placa):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        v.boton_guardar.click()
        otro = fabrica.control()
        svc().guardar(otro, USUARIO, placa.datos, "placa.png", [m.clic for m in v.marcas], parametros(), "G", "automatico")
        assert _sin_ruido(svc().leer(v.ref_de_prueba)) == _sin_ruido(svc().leer(otro))

    def test_despues_de_guardar_la_ventana_queda_en_registro_con_su_linea_y_su_aviso(self, fabrica, dialogos, archivo_placa, clics, bd):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        assert v.estado == "registro" and not v.boton_guardar.isEnabled() and v.etiqueta_registro.text() == f"Guardado: análisis del control {v.ref_de_prueba}, capa reportada verde."
        nuevo = _consulta(bd, "SELECT id FROM analisis_placa_mensual WHERE ref = ?", (v.ref_de_prueba,))[0][0]
        aviso = dialogos.de("information")[-1]
        assert aviso["titulo"] == "Guardar" and aviso["texto"] == f"Análisis guardado para el control {v.ref_de_prueba} (capa verde; id {nuevo})." and aviso["cursor"] is None
        assert [f[0] for f in _auditoria(bd)] == ["guardar"] and _auditoria(bd)[0][1] == USUARIO

    def test_la_auditoria_dice_el_usuario_de_la_sesion(self, fabrica, dialogos, archivo_placa, clics, bd):
        v = analizada(fabrica(usuario="Otra Fisica"), dialogos, archivo_placa, clics)
        v.boton_guardar.click()
        assert _auditoria(bd)[0][1] == "Otra Fisica"

    def test_guardar_otra_vez_pregunta_con_no_por_omision_y_con_no_no_cambia_nada(self, fabrica, dialogos, archivo_placa, clics, bd):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        v.boton_recalcular.click()
        marcar(v, clics)
        dialogos.respuesta = QMessageBox.No
        v.boton_guardar.click()
        pregunta = dialogos.de("question")[0]
        assert pregunta["por_omision"] == QMessageBox.No and pregunta["texto"] == ventana_mod().RESPUESTA_AL_REEMPLAZAR and "REEMPLAZA" in pregunta["texto"]
        assert v.estado == "analizada" and len(_consulta(bd, "SELECT id FROM analisis_placa_mensual")) == 1 and len(_auditoria(bd)) == 1

    def test_con_si_el_anterior_queda_anulado_y_hay_uno_vigente_y_la_auditoria_dice_reemplazo(self, fabrica, dialogos, archivo_placa, clics, bd):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        v.boton_recalcular.click()
        marcar(v, clics)
        elegir_capa(v, "B")
        v.boton_guardar.click()
        assert [(f[2], f[3]) for f in _consulta(bd, "SELECT id, ref, activo, capa FROM analisis_placa_mensual ORDER BY id")] == [(0, "G"), (1, "B")]
        assert [f[0] for f in _auditoria(bd)] == ["guardar", "reemplazo"] and v.estado == "registro"

    def test_un_control_anulado_se_dice_con_el_mensaje_del_servicio_y_la_ventana_queda_como_estaba(self, fabrica, dialogos, archivo_placa, clics, bd):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        _sql(bd, "UPDATE controles SET activo = 0 WHERE id = ?", (v.ref_de_prueba,))
        antes = huella(v)
        v.boton_guardar.click()
        aviso = dialogos.de("warning")[0]
        mensaje = svc().mensaje_bloqueo_edicion(v.ref_de_prueba)
        assert mensaje.endswith("."), "premisa: el mensaje del servicio ya trae su punto final"
        assert aviso["titulo"] == "Guardar" and aviso["texto"] == "No se guardó: " + mensaje, "E1-R2-PROD-03: el mensaje del servicio TAL CUAL, con UN solo punto (no «...eliminado..»)"
        assert v.estado == "analizada" and v.boton_guardar.isEnabled() and huella(v) == antes and not _consulta(bd, "SELECT 1 FROM analisis_placa_mensual")

    def test_un_rechazo_del_servicio_se_dice_tal_cual(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)

        def rechaza(*a, **k):
            raise svc().PlacaMensualError("hace falta otra cosa")
        monkeypatch.setattr(svc(), "guardar", rechaza)
        v.boton_guardar.click()
        assert dialogos.de("warning")[0]["texto"] == "No se guardó: hace falta otra cosa." and v.estado == "analizada"

    @pytest.mark.parametrize("mensaje,esperado", [("hace falta otra cosa", "No se guardó: hace falta otra cosa."), ("el servicio ya trae su punto.", "No se guardó: el servicio ya trae su punto."),
                                                  ("¿esta seguro?", "No se guardó: ¿esta seguro?"), ("¡cuidado!", "No se guardó: ¡cuidado!")])
    def test_un_rechazo_del_servicio_se_dice_con_un_solo_signo_final_lo_traiga_o_no(self, fabrica, dialogos, archivo_placa, clics, monkeypatch, mensaje, esperado):
        """E1-R2-PROD-03 (ronda 2 de la revision): la ventana cierra el mensaje con un punto solo si no termina ya en uno (o en «?» o «!»); un mensaje ajeno nunca queda con dos."""
        v = analizada(fabrica(), dialogos, archivo_placa, clics)

        def rechaza(*a, **k):
            raise svc().PlacaMensualError(mensaje)
        monkeypatch.setattr(svc(), "guardar", rechaza)
        v.boton_guardar.click()
        assert dialogos.de("warning")[0]["texto"] == esperado and v.estado == "analizada"

    @pytest.mark.parametrize("modo", ["automatico", "punto_manual"])
    def test_guardar_pasa_el_sexto_clic_solo_con_el_modo_punto_marcado_y_lo_guardado_dice_el_modo_elegido(self, fabrica, dialogos, archivo_placa, clics, espias, modo):
        """E1-R2-PRU-02 (ronda 2 de la revision). Con un sexto clic marcado y el menu «Piso» en «Automático» el punto sigue en la ventana (para volver a «Punto marcado»), pero NO viaja al servicio: `guardar`
        rechaza un punto marcado con un modo que no es «punto_manual». Sin esa guarda el fisico que marco un sexto clic y volvio al automatico no podria guardar. Con «Punto marcado» el punto SI viaja."""
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        marcar(v, clics[:2])
        v.boton_sexto.click()
        clic(v, 87, 87)
        marcar(v, clics[2:])
        assert v.estado == "analizada" and v.modo_del_piso == "punto_manual" and v.sexto_clic == (87.0, 87.0), "premisa: el sexto clic puso el menu en «Punto marcado»"
        elegir_piso(v, modo)
        assert v.estado == "analizada" and v.modo_del_piso == modo and v.boton_guardar.isEnabled() and v.sexto_clic == (87.0, 87.0)
        v.boton_guardar.click()
        assert v.estado == "registro", (v.estado, [c["texto"] for c in dialogos.llamadas][-2:])
        (args, kwargs), = espias["guardar"]
        assert args[7] == modo and kwargs["punto_manual"] == ((87.0, 87.0) if modo == "punto_manual" else None) and kwargs["referencia_virgen"] is None
        piso = svc().leer(v.ref_de_prueba)["piso"]
        assert piso["modo"] == modo and (list(piso["punto"]) == [87.0, 87.0] if modo == "punto_manual" else piso["punto"] is None)

    def test_un_guardado_que_tarda_pone_el_indicador_y_el_cursor_de_espera_solo_mientras_dura(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        real = svc().guardar
        vistos = []

        def espia(*a, **k):
            vistos.append((QApplication.overrideCursor().shape() if QApplication.overrideCursor() else None, v.indicador.isHidden(), v.indicador.text()))
            return real(*a, **k)
        monkeypatch.setattr(svc(), "guardar", espia)
        v.boton_guardar.click()
        assert vistos == [(Qt.WaitCursor, False, "Guardando...")] and QApplication.overrideCursor() is None and v.indicador.isHidden()


class TestReabrir:
    def test_carga_la_imagen_los_puntos_y_lo_que_mostraba_al_guardar(self, fabrica, dialogos, archivo_placa, clics, placa):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        w = fabrica(ref=v.ref_de_prueba)
        assert w.estado == "registro" and w.nombre_archivo.text() == "placa.png" and np.array_equal(w.eje_imagen.images[0].get_array(), placa.imagen[:, :, ::-1])
        assert [tuple(m["clic"]) for m in w.marcas] == [m.clic for m in v.marcas], "los puntos son los guardados (los diccionarios de `MarcaRefinada.como_dict()`)"
        assert _mostrado(w) == _mostrado(v), "lo que la ventana muestra al reabrir es lo que mostraba al guardar"
        assert w.etiqueta_registro.text().startswith("Análisis guardado: placa.png, ") and w.etiqueta_registro.text().endswith(f", por {USUARIO}; capa reportada verde.")
        assert w.pestanas.currentIndex() == 0 and not w.boton_guardar.isEnabled()

    def test_volver_a_medir_lo_guardado_no_da_diferencias_y_no_avisa(self, fabrica, dialogos, archivo_placa, clics):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        dialogos.llamadas.clear()
        w = fabrica(ref=v.ref_de_prueba)
        assert not dialogos.llamadas and "no coincide" not in w.etiqueta_registro.text()

    def test_una_diferencia_con_lo_guardado_se_dice_en_la_linea_y_en_un_aviso(self, fabrica, dialogos, archivo_placa, clics, bd):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        _sql(bd, "UPDATE analisis_placa_mensual SET fwhm_crossplane_mm = fwhm_crossplane_mm + 0.5 WHERE ref = ?", (v.ref_de_prueba,))
        dialogos.llamadas.clear()
        w = fabrica(ref=v.ref_de_prueba)
        aviso = dialogos.de("warning")[0]
        assert aviso["titulo"] == "Abrir" and aviso["texto"].startswith("Lo recalculado no coincide con lo guardado:\n") and "fwhm_crossplane_mm: guardado " in aviso["texto"]
        assert "Lo recalculado no coincide con lo guardado:" in w.etiqueta_registro.text() and w.estado == "registro"

    def test_una_imagen_guardada_que_ya_no_se_lee_se_dice_y_la_ventana_queda_vacia(self, fabrica, dialogos, archivo_placa, clics, bd):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        _sql(bd, "UPDATE analisis_placa_mensual SET imagen = ? WHERE ref = ?", (b"esto ya no es una imagen", v.ref_de_prueba))
        dialogos.llamadas.clear()
        w = fabrica(ref=v.ref_de_prueba)
        assert w.estado == "vacia" and dialogos.orden() == ["warning"] and dialogos.de("warning")[0]["texto"].startswith("No se pudo abrir el análisis guardado: ")
        assert w.abrir_guardado() is False

    def test_una_imagen_guardada_que_ya_no_se_lee_no_toca_una_ventana_con_otra_imagen(self, fabrica, dialogos, archivo_placa, clics, bd):
        """`abrir_guardado` es publico: llamado con la ventana ocupada (una imagen y dos puntos) y el analisis guardado imposible de abrir, la ventana queda EXACTAMENTE como estaba: todo se lee y se
        calcula antes de tocarla (con una ventana vacia, como la de arriba, no se veria)."""
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        _sql(bd, "UPDATE analisis_placa_mensual SET imagen = ? WHERE ref = ?", (b"esto ya no es una imagen", v.ref_de_prueba))
        w = fabrica(ref=v.ref_de_prueba)                                    # no se abre (la imagen no se lee): queda vacia
        cargar(w, dialogos, archivo_placa)
        marcar(w, clics[:2])
        antes = huella(w)
        dialogos.llamadas.clear()
        assert w.abrir_guardado() is False
        assert huella(w) == antes and w.estado == "imagen" and len(w.marcas) == 2
        assert dialogos.orden() == ["warning"] and dialogos.de("warning")[0]["texto"].startswith("No se pudo abrir el análisis guardado: ")

    def test_se_vuelve_a_medir_con_los_parametros_guardados_y_no_con_los_de_hoy(self, fabrica, dialogos, archivo_placa, clics, placa):
        """El analisis se guardo con otro suavizado y otro `iqr_maximo`: al abrir se mide con ESOS (el pie los dice) y por eso no hay diferencias; con los de hoy habria diferencias."""
        otros = {**parametros(), "suavizado_perfil_mm": 0.0, "iqr_maximo": 12.0}
        ref = fabrica.control()
        svc().guardar(ref, USUARIO, placa.datos, "placa.png", clics, otros, "G", "automatico")
        w = fabrica(ref=ref)
        assert w.estado == "registro" and w._resultado.parametros["suavizado_perfil_mm"] == 0.0 and not dialogos.llamadas, "con los parametros de hoy lo recalculado difiere de lo guardado y se avisaria"
        assert "dispersión de una esquina hasta 12 niveles" in w.pie_de_parametros.text() and "hasta 15 niveles" not in w.pie_de_parametros.text()
        hoy, _b, _m = resultado_directo(placa.datos, clics)
        assert pm().valores_medidos(w._resultado, "G")["fwhm_crossplane_mm"] != pm().valores_medidos(hoy, "G")["fwhm_crossplane_mm"], "premisa: otros parametros dan otro numero"

    def test_se_usa_la_copia_de_la_virgen_guardada_y_se_dice_si_la_vigente_es_otra(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, otro_escaneo_virgen):
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        elegir_piso(v, "virgen")
        marcar(v, clics)
        v.boton_guardar.click()
        sha = escaneo_virgen.referencia.procedencia["sha256"]
        _guardar_referencia(bd, otro_escaneo_virgen)                   # otro equipo guardo una referencia nueva
        w = fabrica(ref=v.ref_de_prueba)
        assert w.modo_del_piso == "virgen" and w._resultado.piso.referencia.procedencia["sha256"] == sha, "manda la copia que se guardo con el analisis (DA-81)"
        assert "La película virgen de referencia vigente es otra («virgen_otro_lote.tif»); este análisis usa la copia que se guardó con él («virgen_lote.tif»)." in w.etiqueta_registro.text()

    def test_la_nota_de_que_la_virgen_vigente_es_otra_se_decide_por_la_huella_del_escaneo_y_no_por_su_nombre(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen, otro_escaneo_virgen):
        """E1-R2-PRU-03 (ronda 2 de la revision). «Es otra» es una pregunta sobre el ESCANEO: dos escaneos distintos del lote pueden llamarse igual («virgen_lote.tif») y el mismo escaneo puede guardarse con otro
        nombre. Comparar por el nombre dejaria al fisico sin el aviso en el primer caso y con un aviso falso en el segundo."""
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        elegir_piso(v, "virgen")
        marcar(v, clics)
        v.boton_guardar.click()
        assert v.estado == "registro"
        nota = "La película virgen de referencia vigente es otra"
        r, otra = escaneo_virgen.referencia, otro_escaneo_virgen.referencia
        assert r.procedencia["sha256"] != otra.procedencia["sha256"]
        # (1) la vigente se llama IGUAL pero es OTRO escaneo (otra huella): se dice
        igual_nombre = dataclasses.replace(otra, procedencia={**otra.procedencia, "archivo": r.procedencia["archivo"]})
        pel().guardar_referencia_virgen(igual_nombre, _carpeta(bd), otro_escaneo_virgen.datos, USUARIO)
        w = fabrica(ref=v.ref_de_prueba)
        assert w.estado == "registro" and nota in w.etiqueta_registro.text(), w.etiqueta_registro.text()
        # (2) la vigente es el MISMO escaneo guardado con otro nombre (la misma huella): no es otra, no se dice
        mismo_escaneo = dataclasses.replace(r, procedencia={**r.procedencia, "archivo": "copia_renombrada.tif"})
        pel().guardar_referencia_virgen(mismo_escaneo, _carpeta(bd), escaneo_virgen.datos, USUARIO)
        x = fabrica(ref=v.ref_de_prueba)
        assert x.estado == "registro" and nota not in x.etiqueta_registro.text(), x.etiqueta_registro.text()

    def test_un_analisis_guardado_con_el_punto_marcado_restaura_el_sexto_clic_y_su_cuadrado(self, fabrica, dialogos, archivo_placa, clics):
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        v.boton_sexto.click()
        clic(v, 87, 87)
        marcar(v, clics)
        v.boton_guardar.click()
        w = fabrica(ref=v.ref_de_prueba)
        assert w.modo_del_piso == "punto_manual" and w.sexto_clic == (87.0, 87.0) and por_gid(w.eje_imagen, "piso:caja:punto") and w._resultado.piso.origen == "manual"

    def test_abrir_con_los_menus_fijos_y_guardar_apagado(self, fabrica, dialogos, archivo_placa, clics):
        w = fabrica(ref=guardada(fabrica(), dialogos, archivo_placa, clics).ref_de_prueba)
        assert not w.selector_capa.isEnabled() and not w.selector_piso.isEnabled() and not w.boton_guardar.isEnabled() and w.linea_regla.isHidden()


# ================================================================================================= 5. Limpiar y Recalcular

class TestLimpiarYRecalcular:
    def test_limpiar_deja_la_ventana_igual_a_una_recien_creada(self, fabrica, dialogos, archivo_placa, clics):
        v = fabrica()
        nueva = huella(v)
        analizada(v, dialogos, archivo_placa, clics)
        elegir_capa(v, "B")
        v.boton_sexto.click()
        clic(v, 87, 87)
        assert huella(v) != nueva, "compuerta: la huella ve lo que cambia"
        v.boton_limpiar.click()
        assert huella(v) == nueva

    def test_limpiar_tambien_libera_un_registro_y_devuelve_los_menus_a_su_valor_inicial(self, fabrica, dialogos, archivo_placa, clics):
        v = fabrica()
        nueva = huella(v)
        guardada(v, dialogos, archivo_placa, clics)
        assert not v.selector_capa.isEnabled()
        v.boton_limpiar.click()
        assert huella(v) == nueva and v.selector_capa.isEnabled() and v.capa_reportada == "G" and v.modo_del_piso == "automatico"

    def test_limpiar_devuelve_el_piso_al_de_omision_aunque_la_virgen_siga_disponible(self, fabrica, dialogos, archivo_placa, clics, bd, escaneo_virgen):
        """Con el punto marcado, Limpiar lo borra y el modo deja de estar disponible (el menu vuelve solo); con la virgen la referencia SIGUE ahi y el modo seguiria disponible: Limpiar debe devolver el
        menu al de omision de todos modos (una ventana recien creada arranca en el automatico)."""
        _guardar_referencia(bd, escaneo_virgen)
        v = fabrica()
        nueva = huella(v)
        analizada(v, dialogos, archivo_placa, clics)
        elegir_piso(v, "automatico")                   # OD.1: con una referencia la ventana nueva arranca en la virgen; el fisico eligio las esquinas
        assert v.modo_del_piso == "automatico" and v.estado == "analizada" and v.selector_piso.model().item(2).isEnabled(), "premisa: las esquinas estan elegidas y la virgen sigue disponible"
        v.boton_limpiar.click()
        assert v.modo_del_piso == "virgen" and v.selector_piso.model().item(2).isEnabled() and huella(v) == nueva

    def test_limpiar_vuelve_a_leer_la_referencia_de_la_pelicula_virgen(self, fabrica, bd, escaneo_virgen):
        """Una ventana recien creada lee la referencia vigente; «Limpiar» la deja igual a una recien creada, asi que la lee otra vez (otro equipo pudo guardar una con la ventana abierta)."""
        v = fabrica()
        assert not v.selector_piso.model().item(2).isEnabled()
        _guardar_referencia(bd, escaneo_virgen)
        v.boton_limpiar.click()
        assert v.selector_piso.model().item(2).isEnabled() and v.selector_piso.itemText(2).startswith("Película virgen «virgen_lote.tif»")

    def test_limpiar_no_toca_lo_guardado(self, fabrica, dialogos, archivo_placa, clics, bd):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        antes = _consulta(bd, "SELECT id, activo, capa FROM analisis_placa_mensual")
        v.boton_limpiar.click()
        assert _consulta(bd, "SELECT id, activo, capa FROM analisis_placa_mensual") == antes and len(_auditoria(bd)) == 1

    def test_recalcular_conserva_la_imagen_y_la_eleccion_de_los_menus_y_borra_puntos_resultado_y_sexto_clic(self, fabrica, dialogos, archivo_placa, clics):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_capa(v, "B")
        v.boton_sexto.click()
        clic(v, 87, 87)
        v.boton_recalcular.click()
        assert v.estado == "imagen" and v.nombre_archivo.text() == "placa.png" and v.marcas == () and v.sexto_clic is None and v._resultado is None and not v.boton_guardar.isEnabled()
        assert v.capa_reportada == "B" and v.modo_del_piso == "automatico", "la capa se conserva; el punto marcado se borra con el sexto clic y el piso vuelve al de omision"
        assert not por_gid(v.eje_imagen, "marca:clic") and v.eje_imagen.images[0].get_array().shape == (2734, 2710, 3) and not v._fig_perfiles.axes
        marcar(v, clics)
        assert v.estado == "analizada", "despues de recalcular se puede marcar otra vez"

    def test_recalcular_con_la_ventana_vacia_no_hace_nada_raro(self, ventana, dialogos):
        ventana.boton_recalcular.click()
        assert ventana.estado == "vacia" and not dialogos.llamadas

    def test_recalcular_libera_los_menus_de_un_registro(self, fabrica, dialogos, archivo_placa, clics):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        v.boton_recalcular.click()
        assert v.estado == "imagen" and v.selector_capa.isEnabled() and v.selector_piso.isEnabled() and v.etiqueta_registro.isHidden()


# ================================================================================================= 6. robustez y memoria

class TestRobustez:
    def test_el_analisis_que_falla_con_un_error_del_motor_se_dice_y_deja_la_ventana_en_fallida(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        def falla(*a, **k):
            raise ValueError("la pelicula no tiene campo")
        monkeypatch.setattr(pm(), "analizar", falla)
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        marcar(v, clics)
        assert v.estado == "fallida" and not v.boton_guardar.isEnabled() and v.marcas and dialogos.orden() == ["warning"]
        assert dialogos.de("warning")[0]["texto"] == "No se pudo analizar: la pelicula no tiene campo. Pulse Recalcular para marcar otra vez."
        v.boton_recalcular.click()
        assert v.estado == "imagen" and v.marcas == ()

    @pytest.mark.parametrize("mensaje", ["la pelicula no tiene campo", "la pelicula no tiene campo."])
    def test_el_error_del_motor_se_dice_con_un_solo_punto_lo_traiga_o_no(self, fabrica, dialogos, archivo_placa, clics, monkeypatch, mensaje):
        """E1-R2-PROD-03 (la misma clase, otro sitio): «No se pudo analizar: <mensaje>. Pulse Recalcular...» no repite el punto de un mensaje que ya lo trae."""
        def falla(*a, **k):
            raise ValueError(mensaje)
        monkeypatch.setattr(pm(), "analizar", falla)
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        marcar(v, clics)
        assert v.estado == "fallida" and dialogos.de("warning")[0]["texto"] == "No se pudo analizar: la pelicula no tiene campo. Pulse Recalcular para marcar otra vez."

    def test_un_error_inesperado_al_analizar_se_dice_con_su_clase_y_no_escapa(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        dialogos.criticos_esperados = True

        def falla(*a, **k):
            raise RuntimeError("algo que nadie previo")
        monkeypatch.setattr(pm(), "analizar", falla)
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        marcar(v, clics)
        assert v.estado == "fallida" and dialogos.de("critical")[0]["texto"] == "Error inesperado al analizar (RuntimeError: algo que nadie previo)." and QApplication.overrideCursor() is None

    @pytest.mark.parametrize("donde", ["seleccionar", "pulsar", "virgen", "capa", "piso", "recalcular", "limpiar", "guardar", "mostrar"])
    def test_ningun_manejador_deja_escapar_una_excepcion(self, fabrica, dialogos, archivo_placa, clics, monkeypatch, donde):
        dialogos.criticos_esperados = True
        v = fabrica()
        if donde in ("capa", "piso", "recalcular", "guardar"):
            analizada(v, dialogos, archivo_placa, clics)
        elif donde == "pulsar":
            cargar(v, dialogos, archivo_placa)

        def falla(*a, **k):
            raise RuntimeError("fallo inyectado")
        titulo = {"seleccionar": "Seleccionar imagen", "pulsar": "Marcar un punto", "virgen": "Película virgen", "capa": "Capa reportada", "piso": "Piso", "recalcular": "Recalcular", "limpiar": "Limpiar",
                  "guardar": "Guardar", "mostrar": "Película virgen"}[donde]
        if donde == "seleccionar":
            monkeypatch.setattr(ventana_mod().QFileDialog, "getOpenFileName", falla)
            v.boton_imagen.click()
        elif donde == "pulsar":
            monkeypatch.setattr(v, "_refinar", falla)
            clic(v, 700, 900)
        elif donde == "virgen":
            monkeypatch.setattr(ventana_mod().QFileDialog, "getOpenFileName", falla)
            v.boton_virgen.click()
        elif donde == "capa":
            monkeypatch.setattr(v, "_aplicar_la_regla", falla)
            elegir_capa(v, "B")
        elif donde == "piso":
            v.boton_sexto.click()
            clic(v, 87, 87)                                                # el punto marcado vuelve a medir: ahora el menu tiene otro modo que elegir
            monkeypatch.setattr(v, "_analizar", falla)
            elegir_piso(v, "automatico")
        elif donde == "recalcular":
            monkeypatch.setattr(v, "_descartar_resultado", falla)
            v.boton_recalcular.click()
        elif donde == "limpiar":
            monkeypatch.setattr(v, "_restablecer_estado", falla)
            v.boton_limpiar.click()
        elif donde == "guardar":
            monkeypatch.setattr(svc(), "leer", falla)
            v.boton_guardar.click()
        else:
            monkeypatch.setattr(v, "refrescar", falla)
            v.show()
        criticos = dialogos.de("critical")
        assert len(criticos) == 1 and criticos[0]["titulo"] == titulo and "RuntimeError: fallo inyectado" in criticos[0]["texto"], dialogos.orden()

    def test_abrir_un_registro_con_la_lectura_rota_no_escapa_y_devuelve_falso(self, fabrica, dialogos, monkeypatch):
        dialogos.criticos_esperados = True
        v = fabrica()
        monkeypatch.setattr(svc(), "leer", lambda ref: (_ for _ in ()).throw(RuntimeError("base rota")))
        assert v.abrir_guardado() is False and dialogos.de("critical")[0]["titulo"] == "Abrir"

    def test_el_cursor_de_espera_solo_esta_puesto_mientras_se_mide_y_el_indicador_se_ve(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        vistos = []
        real = pm().analizar
        v = fabrica()

        def espia(*a, **k):
            cursor = QApplication.overrideCursor()
            vistos.append((cursor.shape() if cursor else None, v.indicador.isHidden(), v.indicador.text()))
            return real(*a, **k)
        monkeypatch.setattr(pm(), "analizar", espia)
        analizada(v, dialogos, archivo_placa, clics)
        assert vistos == [(Qt.WaitCursor, False, "Analizando la imagen...")] and QApplication.overrideCursor() is None and v.indicador.isHidden()

    def test_ningun_cuadro_se_abre_con_el_cursor_de_espera_puesto(self, fabrica, dialogos, archivo_placa, clics):
        v = guardada(fabrica(), dialogos, archivo_placa, clics)
        v.boton_recalcular.click()
        marcar(v, clics)
        v.boton_guardar.click()
        assert dialogos.llamadas and all(c["cursor"] is None for c in dialogos.llamadas)

    def test_cada_manejador_de_una_senal_o_de_un_evento_esta_protegido_por_ast(self):
        arbol = ast.parse(VENTANA_PY.read_text(encoding="utf-8"))
        sin = []
        for clase in (n for n in arbol.body if isinstance(n, ast.ClassDef)):
            for f in (n for n in clase.body if isinstance(n, ast.FunctionDef)):
                if f.name.startswith("_al_") or f.name in ("abrir_guardado", "showEvent"):
                    if not any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "_protegido" for d in f.decorator_list):
                        sin.append(f"{clase.name}.{f.name}")
        assert not sin, f"manejadores sin `_protegido`: {sin}"
        protegidos = [f.name for c in arbol.body if isinstance(c, ast.ClassDef) for f in c.body if isinstance(f, ast.FunctionDef) and f.name.startswith("_al_")]
        assert len(protegidos) >= 9, "compuerta: el censo encuentra los manejadores"


@pytest.fixture
def pagina_entera():
    ruta = _corpus.pelicula("EPSON027")
    if ruta is None:
        pytest.skip("no esta la pagina entera del escaner (EPSON027) en el corpus de peliculas")
    return ruta


class TestUnaPaginaEnteraDelEscaner:
    """EPSON027: 5100 x 6600 px (33 Mpx), la pagina de la que sale ML0. Leida en flotante son 540 MB; la ventana la muestra en RGB uint8 con `nearest` (101 MB; un gris 2D con mapa de color pedia 2 GB)."""

    def test_se_abre_se_dibuja_y_se_analiza_sin_retener_la_pelicula_leida(self, fabrica, dialogos, pagina_entera):
        v = fabrica()
        cargar(v, dialogos, pagina_entera)
        assert v.estado == "imagen"
        matriz = v.eje_imagen.images[0].get_array()
        assert matriz.dtype == np.uint8 and matriz.ndim == 3 and matriz.shape[2] == 3 and matriz.shape[0] * matriz.shape[1] > 30e6 and v.eje_imagen.images[0].get_interpolation() == "nearest"
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            v.lienzo_imagen.draw()
            pico_de_dibujar = tracemalloc.get_traced_memory()[1]
            tracemalloc.reset_peak()
            marcar(v, CLICS_EPSON027)
            pico_de_analizar = tracemalloc.get_traced_memory()[1]
            retenido = tracemalloc.get_traced_memory()[0]
        finally:
            tracemalloc.stop()
        assert v.estado == "analizada" and v._resultado.estado == "ok"
        assert pico_de_dibujar < 500e6, f"dibujar la pagina entera pidio {pico_de_dibujar / 1e6:.0f} MB"
        assert pico_de_analizar < 1.6e9, f"abrir, marcar y analizar la pagina entera pidio un pico de {pico_de_analizar / 1e6:.0f} MB"
        assert v._pelicula is None and retenido < 700e6, f"tras analizar la ventana retiene {retenido / 1e6:.0f} MB (la pelicula leida no se queda)"
        alto, ancho = v._resultado.girada.capas["gris"].shape
        assert alto * ancho < 0.6 * matriz.shape[0] * matriz.shape[1], "el resultado trae la pelicula recortada, no la pagina entera"


# ================================================================================================= 7. por AST: lo que la ventana no hace

@pytest.fixture(scope="module")
def arbol_de_la_ventana():
    return ast.parse(VENTANA_PY.read_text(encoding="utf-8"))


def _importaciones(arbol):
    nombres = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            nombres |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            nombres.add(n.module or "")
            nombres |= {f"{n.module}.{a.name}" for a in n.names}
    return nombres


def _las_tres_capas_a_mano(arbol):
    """[(linea, forma)] de cada sitio donde un arbol escribe las tres capas a mano en vez de leer `pelicula.CAPAS`: una tupla, lista o conjunto de EXACTAMENTE R, G y B (en cualquier orden), un diccionario con
    esas tres claves o la cadena «RGB». Una comparacion suelta (`== "R"`) o una coleccion con otros elementos no cuentan."""
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


NOMBRES_DE_UN_MENSAJE_AJENO = ("error", "motivo", "mensaje")


def _cierres_con_punto_a_mano(arbol):
    """([linea de cada sitio], cuantos mensajes ajenos se vieron): los sitios donde un mensaje ajeno (una variable `error`, `motivo` o `mensaje`) se cierra con un punto escrito a mano: un f-string en que la variable
    va seguida de una constante que empieza por «.» o una suma `... + variable + "."`."""
    def es_mensaje(nodo):
        return isinstance(nodo, ast.Name) and nodo.id in NOMBRES_DE_UN_MENSAJE_AJENO
    sitios, vistos = [], 0
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.JoinedStr):
            for propio, siguiente in zip(nodo.values, nodo.values[1:] + [None]):
                if isinstance(propio, ast.FormattedValue) and es_mensaje(propio.value):
                    vistos += 1
                    if isinstance(siguiente, ast.Constant) and isinstance(siguiente.value, str) and siguiente.value.startswith("."):
                        sitios.append(nodo.lineno)
        elif isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
            if isinstance(nodo.right, ast.Constant) and nodo.right.value == "." and (es_mensaje(nodo.left) or (isinstance(nodo.left, ast.BinOp) and es_mensaje(nodo.left.right))):
                sitios.append(nodo.lineno)
    return sorted(sitios), vistos


def _funciones_que_importan(arbol, paquete):
    """Los nombres de las funciones (a cualquier profundidad) que contienen un `import` o `from ... import` de ese paquete."""
    nombres = set()
    for f in ast.walk(arbol):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for x in ast.walk(f):
                if (isinstance(x, ast.ImportFrom) and (x.module or "").split(".")[0] == paquete) or (isinstance(x, ast.Import) and any(a.name.split(".")[0] == paquete for a in x.names)):
                    nombres.add(f.name)
    return nombres


def _lecturas_del_reloj(arbol):
    """Las lineas donde un arbol LLAMA a `today()`, `now()`, `utcnow()` o `fromtimestamp()`: leer el reloj."""
    return sorted(n.lineno for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("today", "now", "utcnow", "fromtimestamp"))


class TestLaVentanaNoHaceLoQueNoDebe:
    def test_no_tiene_sql_ni_cv2_ni_pyplot(self, arbol_de_la_ventana):
        importado = _importaciones(arbol_de_la_ventana)
        assert not [m for m in importado if m.split(".")[0] in ("sqlite3", "cv2") or m.startswith("PyQt5.QtSql") or "pyplot" in m or m == "matplotlib.use"], sorted(importado)
        sql = [n.value for n in ast.walk(arbol_de_la_ventana) if isinstance(n, ast.Constant) and isinstance(n.value, str) and any(p in n.value.upper() for p in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM", "CREATE TABLE"))]
        assert not sql, f"la ventana no tiene SQL propio: {sql}"
        assert not [n for n in ast.walk(arbol_de_la_ventana) if isinstance(n, ast.Name) and n.id in ("cv2", "plt", "sqlite3")]

    def test_ningun_menu_de_la_ventana_se_crea_suelto_todos_son_el_selector_sin_rueda(self, arbol_de_la_ventana):
        """E1-REV1-PRU-03. Un `QComboBox()` creado sin mas nace con `WheelFocus` y no esta protegido contra la rueda: todo menu de la ventana es un `_SelectorSinRueda`, que fija la politica de foco una vez."""
        creados = [n.func.id for n in ast.walk(arbol_de_la_ventana) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("QComboBox", "_SelectorSinRueda")]
        assert creados.count("_SelectorSinRueda") >= 3 and "QComboBox" not in creados, creados
        clase = next(n for n in arbol_de_la_ventana.body if isinstance(n, ast.ClassDef) and n.name == "_SelectorSinRueda")
        assert any(isinstance(c, ast.Attribute) and c.attr == "setFocusPolicy" for c in ast.walk(clase)), "la clase protegida fija la politica de foco ella misma"

    def test_el_modulo_de_dibujo_no_importa_qt_ni_cv2_ni_pyplot(self):
        importado = _importaciones(ast.parse(DIBUJO_PY.read_text(encoding="utf-8")))
        assert not [m for m in importado if m.split(".")[0] in ("PyQt5", "cv2", "sqlite3") or "pyplot" in m], sorted(importado)

    def test_importa_el_servicio_como_modulo_y_no_la_regla_de_braqui(self, arbol_de_la_ventana):
        importado = _importaciones(arbol_de_la_ventana)
        assert "services.placa_mensual" in importado and not [m for m in importado if "dibujo_posicion_inicial" in m or m.endswith("motivo_para_no_guardar")]
        funciones = [n.name for n in ast.walk(arbol_de_la_ventana) if isinstance(n, ast.FunctionDef)]
        assert "motivo_para_no_guardar" not in funciones, "la regla es del servicio: la ventana no define otra"
        llamadas = [n for n in ast.walk(arbol_de_la_ventana) if isinstance(n, ast.Call)]
        calificadas = [c for c in llamadas if isinstance(c.func, ast.Attribute) and c.func.attr == "motivo_para_no_guardar" and isinstance(c.func.value, ast.Name) and c.func.value.id == "svc"]
        desnudas = [c for c in llamadas if isinstance(c.func, ast.Name) and c.func.id == "motivo_para_no_guardar"]
        assert len(calificadas) >= 3 and not desnudas

    def test_la_ventana_no_decide_la_regla_de_guardar_comparando_un_estado_con_ok(self, arbol_de_la_ventana):
        """Las funciones que deciden si «Guardar» se ofrece o se ejecuta no comparan un estado con «ok»: la regla se le pregunta al servicio. (Otras comparaciones con «ok» son de OTRA cosa: si una
        referencia de pelicula virgen es valida o si el piso se midio.)"""
        reglas = ("_regla_de_guardar", "_al_guardar", "_motivo_de_la_capa_que_se_reporta", "_aplicar_la_regla")
        clase = next(n for n in arbol_de_la_ventana.body if isinstance(n, ast.ClassDef) and n.name == "VentanaPlacaMensual")
        funciones = [n for n in clase.body if isinstance(n, ast.FunctionDef) and n.name in reglas]
        assert sorted(f.name for f in funciones) == sorted(reglas), "compuerta: el censo encuentra las cuatro funciones de la regla"
        comparaciones = [(f.name, c.lineno) for f in funciones for c in ast.walk(f) if isinstance(c, ast.Compare) and any(isinstance(x, ast.Constant) and x.value == "ok" for x in [c.left, *c.comparators])]
        assert not comparaciones, f"la ventana no copia la regla (`estado == \"ok\"`): {comparaciones}"
        assert not [n for n in ast.walk(arbol_de_la_ventana) if isinstance(n, ast.Constant) and n.value == "no medible"], "ni el texto de un estado del motor: la regla se pregunta al servicio"

    def test_las_constantes_por_omision_solo_son_el_valor_inicial_de_los_menus(self, arbol_de_la_ventana):
        donde = {}
        for f in (n for n in ast.walk(arbol_de_la_ventana) if isinstance(n, ast.FunctionDef)):
            for a in ast.walk(f):
                if isinstance(a, ast.Attribute) and a.attr in ("CAPA_POR_OMISION", "MODO_DEL_PISO_POR_OMISION", "modo_efectivo"):
                    donde.setdefault(a.attr, set()).add(f.name)
        # OD.1: el modo con que arranca el menu «Piso» lo da `pelicula.modo_efectivo` (la UNICA regla, que lee la constante); la ventana la pregunta en UN solo sitio y no lee la constante.
        assert donde == {"CAPA_POR_OMISION": {"_restablecer_estado"}, "modo_efectivo": {"_modo_por_omision"}}, donde

    def test_no_escribe_las_tres_capas_a_mano_ni_ningun_modo_del_piso_suelto(self, arbol_de_la_ventana):
        assert not _las_tres_capas_a_mano(arbol_de_la_ventana) and not _las_tres_capas_a_mano(ast.parse(DIBUJO_PY.read_text(encoding="utf-8")))
        assert _las_tres_capas_a_mano(ast.parse('capas = ("R", "G", "B")')) == [(1, "Tuple")] and _las_tres_capas_a_mano(ast.parse('for c in "RGB": pass')), "el guardia ve lo que busca"

    def test_el_titulo_de_un_perfil_se_define_una_vez_y_la_ventana_lo_llama(self, arbol_de_la_ventana):
        definiciones = [n for n in ast.walk(ast.parse(DIBUJO_PY.read_text(encoding="utf-8"))) if isinstance(n, ast.FunctionDef) and n.name == "titulo_del_perfil"]
        assert len(definiciones) == 1
        llamadas = [c for c in ast.walk(arbol_de_la_ventana) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "titulo_del_perfil"]
        assert llamadas, "la ventana vuelve a escribir los titulos con la funcion de dibujo, no con otro texto"
        docstrings = {id(n.body[0].value) for n in ast.walk(arbol_de_la_ventana) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body and isinstance(n.body[0], ast.Expr)
                      and isinstance(n.body[0].value, ast.Constant)}
        assert not [n for n in ast.walk(arbol_de_la_ventana) if isinstance(n, ast.Constant) and isinstance(n.value, str) and "FWHM" in n.value and id(n) not in docstrings], \
            "ningun texto de un titulo escrito en la ventana"

    def test_guardar_se_llama_con_la_capa_y_el_modo_sin_valor_por_omision(self, arbol_de_la_ventana):
        llamadas = [c for c in ast.walk(arbol_de_la_ventana) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "guardar" and isinstance(c.func.value, ast.Name)
                    and c.func.value.id == "svc"]
        assert len(llamadas) == 1 and len(llamadas[0].args) == 8 and {k.arg for k in llamadas[0].keywords} == {"punto_manual", "referencia_virgen"}
        nombres = [a.id if isinstance(a, ast.Name) else None for a in llamadas[0].args]
        assert nombres[-2:] == ["capa", "modo"], "la capa y el modo llegan como argumentos de la llamada, no como constantes"

    @pytest.mark.parametrize("modulo", ["la ventana", "el modulo de dibujo"])
    def test_ningun_mensaje_ajeno_se_cierra_con_un_punto_escrito_a_mano(self, arbol_de_la_ventana, modulo):
        """E1-R2-PROD-03, la clase. Un mensaje que viene de otra capa (`error`, `motivo`, `mensaje`) ya trae su puntuacion: un punto literal pegado detras lo duplica («...eliminado..»). Se cierra con
        `con_punto_final`, que lo agrega solo si falta."""
        arbol = arbol_de_la_ventana if modulo == "la ventana" else ast.parse(DIBUJO_PY.read_text(encoding="utf-8"))
        sitios, vistos = _cierres_con_punto_a_mano(arbol)
        assert vistos >= (5 if modulo == "la ventana" else 1), f"compuerta: el guardia ve los mensajes ajenos de {modulo} ({vistos})"
        assert not sitios, f"{modulo}: un mensaje ajeno cerrado con un punto escrito a mano (lineas {sitios}): usar `con_punto_final`"
        muestra = ast.parse('a = f"No se guardo: {error}."\nb = "Prefijo: " + motivo + "."\nc = f"{valor}."\nd = f"({error})."')
        assert _cierres_con_punto_a_mano(muestra) == ([1, 2], 2), "el guardia ve las dos formas del defecto y no confunde un valor con un mensaje"

    def test_el_docstring_del_modulo_de_dibujo_nombra_cada_funcion_en_la_que_entra_matplotlib(self):
        """E1-R2-PROD-06, la clase. El docstring dice dónde entra `matplotlib` («solo dentro de la funcion que...»): se deriva del codigo qué funciones lo importan y el docstring las nombra a todas."""
        arbol = ast.parse(DIBUJO_PY.read_text(encoding="utf-8"))
        funciones = _funciones_que_importan(arbol, "matplotlib")
        assert {"colorear", "dibujar_capas"} <= funciones, f"compuerta: el censo encuentra las dos funciones que dibujan el mapa de color ({sorted(funciones)})"
        doc = ast.get_docstring(arbol)
        assert all(f"`{nombre}`" in doc for nombre in funciones), f"el docstring del modulo no nombra {sorted(n for n in funciones if f'`{n}`' not in doc)}"
        assert sorted(_funciones_que_importan(ast.parse("def f():\n    from matplotlib import cm\ndef g():\n    import numpy"), "matplotlib")) == ["f"], "el censo ve un import dentro de una funcion"

    def test_ninguna_prueba_de_e1_lee_el_reloj(self):
        """E1-R2-PRU-04, la clase. Una prueba que compara contra `date.today()` cae si la medianoche cruza entre construir lo que compara y la asercion (DP-94, DP-155). Las fechas de las pruebas de E.1 son
        constantes (`FECHA_DE_PRUEBA`) y el reloj de la ventana se fija (`HoyFijo`)."""
        raiz = Path(__file__).resolve().parent
        archivos = ["_e1_ayudas.py", "test_e1_ventana_placa_mensual.py", "test_e1_menus_guardar_reabrir.py", "test_e1_capa_no_medible.py"]
        lecturas = {a: _lecturas_del_reloj(ast.parse((raiz / a).read_text(encoding="utf-8"))) for a in archivos}
        assert all((raiz / a).is_file() for a in archivos) and not any(lecturas.values()), f"una prueba lee el reloj: {lecturas}"
        assert _lecturas_del_reloj(ast.parse("x = date.today().isoformat()\ny = datetime.now()")) == [1, 2], "el guardia ve lo que busca"

    def test_los_parametros_con_que_mide_son_una_copia_de_los_del_motor(self, arbol_de_la_ventana):
        f = next(n for n in ast.walk(arbol_de_la_ventana) if isinstance(n, ast.FunctionDef) and n.name == "_parametros")
        assert "VALORES_DE_LA_GEOMETRIA" in ast.dump(f) and "deepcopy" in ast.dump(f)
