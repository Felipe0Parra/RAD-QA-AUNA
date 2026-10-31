"""E.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-83 a DA-86, PD1 a PD3): la ventana del analisis mensual de aceleradores, `VentanaPlacaMensual(ref, equipo, usuario, parent)`, en
`ui/paginasControles/PruebasMensuales/placa_mensual.py`, con sus dibujos y textos puros en `analisisImagenes/dibujo_placa_mensual.py`. Este archivo prueba lo que el fisico VE; los menus, la pelicula
virgen, guardar y reabrir estan en `test_e1_menus_guardar_reabrir.py` y la regla de D.1b (una capa no medible no se ofrece) en `test_e1_capa_no_medible.py`.

CAUSA. Hasta E.1 el motor nuevo (C.1 a C.3) y su servicio (D.1) no tienen pantalla: el fisico no puede abrir la pelicula del control, marcar los cinco puntos del campo luminoso ni ver lo que se midio. El
analisis viejo (un lienzo con cinco graficas que se recorren con «Anterior/Siguiente», un texto HTML, la imagen en `Reds`) no muestra capas, piso, barridos ni placa acondicionada, y escondia el umbral que
movio el desfase 19 mm (R10): PD1, nada escondido que cambie el numero.

LO QUE SE GARANTIZA, todo POR EL CAMINO DEL USUARIO (clics reales en el lienzo, botones reales, la pelicula sintetica de PF.0, una BD temporal; nunca una BD de referencia) y cada cosa contra una verdad que
NO sale de la ventana (el motor sobre esos mismos bytes: `leer_pelicula` + `refinar_marca` + `analizar` + `barrido`):
  1. LA VENTANA ARRANCA. Cinco pestanas con sus nombres, los controles de la barra (imagen, «Marcar pelicula sin irradiar», «Piso», «Pelicula virgen...», «Capa reportada», Recalcular, Limpiar, Guardar),
     «Guardar» apagado, nada dibujado, el pie de parametros fijos escrito, y el control sin analisis guardado no abre nada.
  2. CARGAR LA IMAGEN. En su color original (RGB uint8 con `nearest`: los mismos pixeles del archivo), con lo que el archivo declara (formato, bits, tamano, resolucion, transparencia); atomico (si no
     se lee, todo queda como estaba); un TIFF de 16 bits se muestra en 8 y la resolucion de un editor o distinta de 600 dpi se dice.
  3. LOS CLICS. Solo cuentan con una imagen abierta, el boton izquierdo, la lupa y el desplazar apagados, dentro de la imagen y sin doble clic; se guardan a 3 decimales; el quinto analiza UNA vez; el
     orden de los clics no importa; el analisis falla con aviso (nunca con una excepcion) y el cursor de espera y el indicador estan puestos solo mientras se mide.
  4. «MARCAR PELICULA SIN IRRADIAR». El clic siguiente es el SEXTO: nunca entra a la clasificacion de los cinco puntos, pone el menu «Piso» en «Punto marcado», dibuja su cuadrado de 3 x 3 mm y, con los cinco
     puntos hechos, vuelve a medir con el.
  5. EL ANALISIS ES EL DEL MOTOR (los valores de cada capa, el piso, el barrido) y se mide con los parametros de fabrica (todos, la base incluida), sin ningun control que los cambie.
  6. CADA PESTANA DIBUJA LO QUE DICE. (1) la imagen con los cinco clics, su punto refinado y su circulo de busqueda, el recuadro del campo luminoso (los vertices de `recuadro_luminoso`, los mismos del PDF),
     las diagonales, el cruce, el reticulo, las dos bandas de 1 mm, la zona central y la region del piso; al lado los dos perfiles del GRIS con todas sus lineas y debajo la tabla de sus desfases;
     (2) las tres capas acondicionadas en `jet` con la cruz, la cuadricula, el recuadro y la region del piso; (3) los ocho perfiles completos (la pelicula a los dos lados del campo, en mm desde el cruce)
     y su tabla por capa y eje, cada capa por separado y sin ninguna marca que las compare (PD3); (4) los barridos (todas las bandas, la media, la mediana, el corte central, la zona; sin selector, PD2) y su
     tabla; (5) la cuadratura (el recuadro contra el cuadrado perfecto, las desviaciones ampliadas x 20 y rotuladas) y su tabla.
  7. PD1 POR CENSO. Cada parametro de `VALORES_DE_LA_GEOMETRIA` tiene su trazo o su rotulo (los 40; el censo por AST de los que leen el motor y el piso se deriva del codigo) y cada entrada esta de verdad en la
     ventana; ningun control cambia un numero (los unicos controles editables son los de la imagen, los clics, el sexto, los dos menus y los botones); ningun texto lleva simbolos de correcto o incorrecto (DA-18)
     ni unidades entre parentesis, y la ventana no da veredicto (PD3, DA-83: solo informativa).

Trampa 2 (todo `QMessageBox` y todo cuadro de dialogo se parcha: la fixture `dialogos`), Trampa 9 (cada ventana se cierra con la receta completa; la huella no mira internos de Qt), Trampa 10 (ningun
`lru_cache`: los resultados caros son fixtures de modulo y nadie los muta; la ventana compartida `solo_lectura` solo se MIRA, y una prueba de cierre del modulo lo comprueba).
Rojo contra HEAD (2b75c30): la ventana y el modulo de dibujo no existen; las pruebas importan POR DENTRO (`ventana_mod()`), asi que cada una cae con su error de importacion.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import copy
import dataclasses
import math
import re
import shutil
import textwrap
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.path import Path as RutaMpl
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton, QSlider, QSpinBox,
                             QTableWidget)

import _corpus
import _placa_mensual_sintetica as gen
import data.ManejoDatos.conection as conection_mod
from _e1_ayudas import (ADJETIVO, CAPAS, EQUIPO, MOTOR_PY, PELICULA_PY, PESTANAS, USUARIO, TAM, _cursor_limpio, analizada, app, archivo_placa, cargar, cerrar,  # noqa: F401
                        clic, con_gid, dialogos, dibujo_mod, elegir_capa, elegir_piso, etiquetas, fabrica, huella, marcar, pel, pm, por_gid, recorrer, resultado_directo, sin_simbolos, svc,
                        texto_de_la_tabla, todos_los_textos, ventana, ventana_mod)
from data.ManejoDatos.conection import Conexion
from test_d1_guardado_placa_mensual import _control, _P, bd, clics, oraculos, placa, plantilla, punto_manual, virgen  # noqa: F401  (fixtures y ayudas de D.1)


# ------------------------------------------------------------------------------------------------------ el oraculo: el motor, directamente

from _e1_ayudas import con_la_base_de_pixel  # noqa: F401  (fixture)


# OD.1 (DA-87): la netOD es la base por omision del analisis y el rojo de la sintetica esta recortado en ella (la capa roja ya no se mide ni se guarda). Las pruebas de la
# ventana de E.1 prueban el flujo (marcar, medir, guardar, reabrir, la regla de D.1b) con las TRES capas medibles, asi que fijan la base de VALOR DE PIXEL en todo el
# archivo; la ventana en netOD (el menu del piso, el cuadro de la virgen, los perfiles dibujados en la base) la prueba `test_od1_densidad_optica.py`.
@pytest.fixture(scope="module", autouse=True)
def _base_de_pixel(con_la_base_de_pixel):
    yield


@pytest.fixture(scope="module")
def directo(placa, clics):
    """El analisis del motor de la sintetica A, una vez por modulo (sus arreglos pesan; nadie lo muta)."""
    resultado, barrido, marcas = resultado_directo(placa.datos, clics)
    return SimpleNamespace(resultado=resultado, barrido=barrido, marcas=marcas)


@pytest.fixture(scope="module")
def solo_lectura(app, plantilla, tmp_path_factory, placa, clics):
    """UNA ventana analizada por el camino del usuario (la imagen, cinco clics reales), COMPARTIDA por las pruebas que solo la MIRAN: construirla cuesta ~2 s y hay decenas de preguntas que hacerle. Ninguna
    prueba que use esta fixture cambia nada de ella (la ultima prueba del archivo lo comprueba con la huella). Tiene su propia BD temporal y sus propios dialogos parchados."""
    carpeta = tmp_path_factory.mktemp("e1_solo_lectura")
    ruta_bd = str(carpeta / "e1.db")
    shutil.copy(plantilla, ruta_bd)
    ruta_png = carpeta / "placa.png"
    ruta_png.write_bytes(placa.datos)
    mp = pytest.MonkeyPatch()
    mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta_bd)
    previo = Conexion._instance
    Conexion._instance = object.__new__(Conexion)
    avisos = []
    for nombre in ("warning", "information", "critical"):
        mp.setattr(QMessageBox, nombre, staticmethod(lambda *a, _n=nombre, **k: avisos.append((_n, a[1:])) or QMessageBox.Ok))
    mp.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: avisos.append(("question", a[1:])) or QMessageBox.Yes))
    mp.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(ruta_png), "")))
    v = ventana_mod().VentanaPlacaMensual(_control(ruta_bd), EQUIPO, USUARIO)
    v.resize(1380, 880)
    v.boton_imagen.click()
    marcar(v, clics)
    assert v.estado == "analizada" and not avisos, (v.estado, avisos)
    for lienzo in (v.lienzo_imagen, v.lienzo_gris, v.lienzo_capas, v.lienzo_perfiles, v.lienzo_barridos, v.lienzo_cuadratura):
        lienzo.draw()                      # los limites de un eje de aspecto igual se ajustan al DIBUJAR: la huella de referencia se toma con todo ya dibujado
    estado = SimpleNamespace(v=v, avisos=avisos, huella_al_crear=huella(v), ruta_bd=ruta_bd, ruta_png=str(ruta_png))
    yield estado
    cerrar(v)
    mp.undo()
    Conexion._instance = previo


def _grupo(v):
    """Los ocho ejes de los perfiles de la pestana 3 como {(capa, eje): eje}, en el orden de la figura (R, G, B y el gris; crossplane e inplane)."""
    ejes = list(v._fig_perfiles.axes)
    assert len(ejes) == 8, f"la pestana 3 tiene ocho perfiles, no {len(ejes)}"
    clave = [(c, e) for c in (*CAPAS, "gris") for e in ("crossplane", "inplane")]
    return dict(zip(clave, ejes))


def _con_signo(x):
    """El numero con signo y tres decimales, y nunca «-0.000» ni «+0.000»: lo que redondea a cero no tiene signo (la regla de `numero`, escrita aqui como el oraculo)."""
    texto = f"{x:+.3f}"
    return texto if float(texto) != 0 else texto.lstrip("+-")


def _normalizar_texto(texto):
    return " ".join(texto.split())


LADOS_A_MANO = ("superior", "derecho", "inferior", "izquierdo")
ESQUINAS_A_MANO = (("UL", "superior izquierda"), ("UR", "superior derecha"), ("DR", "inferior derecha"), ("DL", "inferior izquierda"))


def _filas_de_la_cuadratura_esperadas(g):
    """E1-REV1-PRU-01. Las 15 filas (rotulo, valor, cuadrado perfecto, diferencia) de la tabla de la pestana 5 para esa geometria, con la aritmetica del plan escrita AQUI (no con `filas_de_la_cuadratura`): el
    lado perfecto es el medio de los cuatro lados, la inclinacion y el angulo girado se comparan con 0, los angulos interiores con 90 y las diagonales con el lado perfecto por la raiz de 2; la diferencia
    es SIEMPRE «medido menos perfecto», con signo."""
    lado = sum(g.lados_mm[n] for n in LADOS_A_MANO) / 4.0
    diagonal = lado * math.sqrt(2.0)
    filas = [[f"Lado {n} [mm]", f"{g.lados_mm[n]:.3f}", f"{lado:.3f}", _con_signo(g.lados_mm[n] - lado)] for n in LADOS_A_MANO]
    filas += [[f"Inclinación del lado {n} [°]", _con_signo(g.inclinacion_de_los_lados_grados[n]), "0.000", _con_signo(g.inclinacion_de_los_lados_grados[n])] for n in LADOS_A_MANO]
    filas += [[f"Ángulo interior {texto} [°]", f"{g.angulos_interiores_grados[e]:.3f}", "90.000", _con_signo(g.angulos_interiores_grados[e] - 90.0)] for e, texto in ESQUINAS_A_MANO]
    filas += [[f"Diagonal {n} [mm]", f"{v:.3f}", f"{diagonal:.3f}", _con_signo(v - diagonal)] for n, v in zip(("principal", "secundaria"), g.diagonales_mm)]
    filas.append(["Ángulo girado [°]", _con_signo(g.angulo_grados), "0.000", _con_signo(g.angulo_grados)])
    return filas


# ================================================================================================= 1. la ventana arranca

class TestLaVentanaArranca:
    def test_tiene_las_cinco_pestanas_con_sus_nombres_y_en_ese_orden(self, ventana):
        assert ventana.pestanas.count() == 5 and [ventana.pestanas.tabText(i) for i in range(5)] == list(PESTANAS)
        assert ventana.pestanas.currentIndex() == 0

    def test_la_barra_tiene_los_controles_del_plan_con_su_texto(self, ventana):
        assert ventana.boton_imagen.text() == "Seleccionar imagen" and ventana.boton_sexto.text() == "Marcar película sin irradiar"
        assert ventana.boton_virgen.text() == "Película virgen..." and ventana.boton_recalcular.text() == "Recalcular"
        assert ventana.boton_limpiar.text() == "Limpiar" and ventana.boton_guardar.text() == "Guardar"
        assert ventana.etiqueta_piso_menu.text() == "Piso:" and ventana.etiqueta_capa.text() == "Capa reportada:"
        assert ventana.boton_sexto.isCheckable() and not ventana.boton_sexto.isChecked()

    def test_arranca_vacia_con_guardar_apagado_y_sin_nada_dibujado(self, ventana):
        assert ventana.estado == "vacia" and not ventana.boton_guardar.isEnabled() and ventana.marcas == () and ventana.sexto_clic is None
        assert ventana.nombre_archivo.text() == "Ninguna imagen" and ventana.nombre_archivo.isReadOnly()
        for figura in (ventana._fig_gris, ventana._fig_capas, ventana._fig_perfiles, ventana._fig_barridos):
            assert not figura.axes
        assert not ventana.eje_imagen.images and not ventana.eje_cuadratura.lines
        assert all(t.rowCount() == 0 for t in (ventana.tabla_desfases, ventana.tabla_perfiles, ventana.tabla_barridos, ventana.tabla_cuadratura))
        assert ventana.indicador.isHidden()

    def test_sin_resultado_no_hay_motivo_de_la_capa_que_se_reporta(self, ventana):
        assert ventana._resultado is None and ventana._motivo_de_la_capa_que_se_reporta() is None

    def test_el_tamano_inicial_se_acota_a_la_pantalla_y_sin_pantalla_es_el_declarado(self, monkeypatch):
        modulo = ventana_mod()
        ancho, alto = modulo.TAMANO_DE_LA_VENTANA
        pequena = SimpleNamespace(availableGeometry=lambda: SimpleNamespace(width=lambda: 1000, height=lambda: 600))
        monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: pequena))
        assert ancho > 950 and alto > 552, "premisa: la pantalla de la prueba es mas chica que la ventana"
        assert modulo._tamano_inicial() == (950, 552), "el 95 % del ancho y el 92 % del alto de la pantalla"
        monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: None))
        assert modulo._tamano_inicial() == (ancho, alto), "sin pantalla se abre con el tamano declarado"

    def test_las_lineas_de_informacion_estan_escondidas_si_estan_vacias(self, ventana):
        for etiqueta in (ventana.linea_regla, ventana.etiqueta_imagen, ventana.etiqueta_marcas, ventana.etiqueta_piso, ventana.etiqueta_registro, ventana.nota_pestana1, ventana.nota_pestana2):
            assert etiqueta.text() == "" and etiqueta.isHidden(), etiqueta.objectName() or type(etiqueta).__name__

    def test_dice_a_cuantos_dpi_se_escanea(self, ventana):
        assert ventana.etiqueta_escaneo.text() == "Escanear a 600 dpi"

    def test_el_pie_de_parametros_fijos_esta_escrito_desde_el_arranque(self, ventana):
        pie = ventana.pie_de_parametros.text()
        assert pie.startswith("Parámetros fijos del método (se guardan con cada análisis; no se ajustan en pantalla):")
        assert pie == dibujo_mod().texto_de_parametros()

    def test_el_titulo_dice_el_equipo(self, fabrica):
        assert EQUIPO in fabrica().windowTitle() and "campo luminoso" in fabrica().windowTitle()
        assert "campo luminoso" in fabrica(equipo="").windowTitle() and "-" not in fabrica(equipo="").windowTitle()

    def test_es_una_ventana_de_primer_nivel_aunque_tenga_madre(self, fabrica, app):
        madre = QApplication.activeWindow() or fabrica()
        w = fabrica(parent=madre)
        assert w.isWindow() and w.parent() is madre

    def test_acepta_el_usuario_como_texto_o_como_objeto_de_sesion(self, fabrica):
        class Sesion:
            _nombre = "Nombre de la sesion"
        assert fabrica(usuario=USUARIO).usuario == USUARIO and fabrica(usuario=Sesion()).usuario == "Nombre de la sesion" and fabrica(usuario=object()).usuario is None

    def test_un_control_sin_analisis_guardado_no_abre_nada(self, fabrica, dialogos):
        v = fabrica()
        assert v.abrir_guardado() is False and v.estado == "vacia" and not dialogos.llamadas

    def test_los_menus_arrancan_en_lo_que_dicen_las_constantes(self, ventana):
        # OD.1: la constante del modo de omision es «virgen» y el menu arranca en `modo_efectivo`: sin una pelicula virgen cargada (esta ventana no tiene ninguna) son las esquinas
        assert ventana.capa_reportada == pel().CAPA_POR_OMISION == "G" and pel().MODO_DEL_PISO_POR_OMISION == "virgen" and ventana.modo_del_piso == pel().modo_efectivo(None, None) == "automatico"
        assert ventana.selector_capa.isEnabled() and ventana.selector_piso.isEnabled()
        # `_restablecer_estado` (lo llaman el constructor y Limpiar, y los dos lo siguen con `refrescar`, que devolveria al modo de omision uno que no esta disponible) deja los dos menus en su valor inicial
        # POR SI SOLO: sin esta llamada directa una rotura de esa linea quedaria tapada por `refrescar`.
        ventana._poner_capa("B")
        ventana._poner_modo("punto_manual")                      # `setCurrentIndex` admite el indice aunque el modo no este disponible; `refrescar` es quien lo devuelve
        ventana._restablecer_estado()
        assert ventana.capa_reportada == "G" and ventana.modo_del_piso == "automatico"


# ================================================================================================= 2. cargar la imagen

@pytest.fixture(scope="module")
def tiff_16(tmp_path_factory):
    """Una pelicula mensual de 16 bits por canal (TIFF): se muestra en 8 bits y la ventana dice que es de 16."""
    ruta = tmp_path_factory.mktemp("e1_tiff16") / "placa16.tif"
    ruta.write_bytes(gen.generar("tiff", bits=16, variante="A", seed=2).datos)
    return str(ruta)


@pytest.fixture(scope="module")
def png_con_alfa(tmp_path_factory):
    """Una pelicula con canal alfa y una zona transparente (lo transparente es sin dato, A.1)."""
    imagen, _verdad = gen.generar_arreglo(bits=8, alfa=True, variante="A", seed=2)
    imagen = np.array(imagen)
    imagen[:50, :80, 3] = 0
    ruta = tmp_path_factory.mktemp("e1_alfa") / "placa_alfa.png"
    ruta.write_bytes(gen.codificar(imagen, "png", 600))
    return str(ruta), 50 * 80


class TestCargarLaImagen:
    def test_la_imagen_se_ve_en_su_color_original_con_los_mismos_pixeles_del_archivo(self, ventana, dialogos, archivo_placa, placa):
        cargar(ventana, dialogos, archivo_placa)
        imagen = ventana.eje_imagen.images[0]
        assert imagen.get_array().dtype == np.uint8 and imagen.get_interpolation() == "nearest"
        assert np.array_equal(imagen.get_array(), placa.imagen[:, :, ::-1]), "RGB uint8: los mismos pixeles del archivo (BGR de OpenCV puesto en R, G, B)"

    def test_la_imagen_cargada_deja_la_ventana_lista_para_marcar(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        assert ventana.estado == "imagen" and ventana.nombre_archivo.text() == "placa.png" and ventana.marcas == () and not ventana.boton_guardar.isEnabled()
        assert ventana.eje_imagen.get_xlabel() == "columna de la imagen [px]" and ventana.eje_imagen.get_ylabel() == "fila de la imagen [px]"
        assert ventana.pestanas.currentIndex() == 0 and not dialogos.llamadas

    def test_dice_lo_que_el_archivo_declara(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        assert ventana.etiqueta_imagen.text() == "PNG, 8 bits por canal, 2710 × 2734 px. resolución declarada 600 dpi, igual que la del procedimiento."

    def test_el_archivo_no_dice_donde_estaba_la_carpeta_de_quien_lo_subio(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        assert ventana.nombre_archivo.text() == "placa.png" and "/" not in ventana.nombre_archivo.text()

    @pytest.mark.parametrize("dpi,debe_decir", [(96, "lo que escribe un editor al guardar un recorte: se usa la del procedimiento, 600 dpi"),
                                                (300, "el procedimiento es de 600 dpi: sin esa escala no hay milímetros ni medidas")])
    def test_una_resolucion_de_editor_o_distinta_se_dice(self, ventana, dialogos, tmp_path, placa, dpi, debe_decir):
        ruta = tmp_path / f"a_{dpi}.png"
        ruta.write_bytes(gen.codificar(placa.imagen, "png", dpi))
        cargar(ventana, dialogos, str(ruta))
        assert debe_decir in ventana.etiqueta_imagen.text() and f"el archivo declara {dpi}" in ventana.etiqueta_imagen.text()

    @pytest.mark.parametrize("dpi,hay_escala", [(600, True), (96, True), (72, True), (300, False), (200, False), (1200, False)])
    def test_la_linea_de_las_marcas_habla_de_milimetros_solo_si_hay_escala_y_si_no_los_dice_en_pixeles(self, ventana, dialogos, tmp_path, placa, clics, directo, dpi, hay_escala):
        """E1-PROD-02 (ronda 1 de la revision). Con un archivo que declara OTRA resolucion (300 dpi...) la linea de la imagen dice «sin esa escala no hay milimetros ni medidas»; la linea de las marcas no
        puede decir a la vez «el punto se movio de 0.001 a 0.023 mm del clic» (milimetros de una escala que no hay): dos textos de la misma pantalla se contradecian. Cuanto se movio el punto es un hecho
        de la imagen y sin escala se dice en PIXELES (el motor lo da: `desplazamiento_px`); con escala (la del procedimiento: 600 dpi, o lo que un editor escribe al recortar) sigue en milimetros. El
        oraculo es el motor sobre esos bytes y esos clics, formateado aqui a mano; los pixeles que se mueve un punto no dependen de lo que el archivo declare."""
        ruta = tmp_path / f"a_{dpi}.png"
        ruta.write_bytes(gen.codificar(placa.imagen, "png", dpi))
        cargar(ventana, dialogos, str(ruta))
        assert ("sin esa escala no hay milímetros ni medidas" in ventana.etiqueta_imagen.text()) == (not hay_escala), "premisa: la linea de la imagen dice si hay escala"
        marcar(ventana, clics)
        refinadas = [m for m in directo.marcas if m.refinada]
        assert len(refinadas) == 5 and all(m.refinada for m in ventana.marcas), "compuerta: las cinco marcas se refinan (hay un rango de movimientos que decir)"
        if hay_escala:
            mm = [m.desplazamiento_mm for m in refinadas]
            esperado = f"Marcas 5 de 5. Refinadas: 1, 2, 3, 4, 5; el punto se movió de {min(mm):.3f} a {max(mm):.3f} mm del clic."
        else:
            px = [m.desplazamiento_px for m in refinadas]
            esperado = f"Marcas 5 de 5. Refinadas: 1, 2, 3, 4, 5; el punto se movió de {min(px):.2f} a {max(px):.2f} px del clic."
        assert ventana.etiqueta_marcas.text() == esperado
        assert ("mm" in ventana.etiqueta_marcas.text()) == hay_escala, "sin escala la linea de las marcas no habla de milimetros"

    def test_un_tiff_de_16_bits_se_muestra_en_8_y_la_ventana_dice_que_es_de_16(self, ventana, dialogos, tiff_16):
        cargar(ventana, dialogos, tiff_16)
        assert ventana.estado == "imagen" and "TIFF, 16 bits por canal" in ventana.etiqueta_imagen.text()
        imagen = ventana.eje_imagen.images[0].get_array()
        assert imagen.dtype == np.uint8 and imagen.ndim == 3 and imagen.shape[2] == 3, "una imagen de 16 bits no se pinta en 16: se muestra en niveles de 8 bits"
        pelicula = pel().leer_pelicula(Path(tiff_16).read_bytes())
        for k, capa in enumerate("RGB"):
            assert np.array_equal(imagen[:, :, k], np.clip(np.rint(getattr(pelicula, capa)), 0, 255).astype(np.uint8)), f"la capa {capa} mostrada es la de la pelicula en niveles de 8 bits"

    def test_lo_transparente_se_cuenta_y_no_se_rechaza_la_imagen(self, ventana, dialogos, png_con_alfa):
        ruta, cuantos = png_con_alfa
        cargar(ventana, dialogos, ruta)
        assert ventana.estado == "imagen" and f"{cuantos} píxeles transparentes, que son sin dato" in ventana.etiqueta_imagen.text()

    def test_cancelar_el_cuadro_de_archivo_no_cambia_nada(self, ventana, dialogos):
        antes = huella(ventana)
        cargar(ventana, dialogos, "")
        assert huella(ventana) == antes and not dialogos.llamadas

    def test_un_archivo_que_no_es_una_imagen_se_dice_y_la_ventana_queda_igual(self, fabrica, dialogos, tmp_path, archivo_placa, clics):
        malo = tmp_path / "texto.png"
        malo.write_bytes(b"esto no es una imagen")
        v = analizada(fabrica(), dialogos, archivo_placa, clics)          # con una imagen, cinco puntos y su analisis: la carga que falla no puede tocar nada de eso (una ventana vacia no lo probaria)
        antes = huella(v)
        cargar(v, dialogos, str(malo))
        assert huella(v) == antes and v.estado == "analizada" and len(v.marcas) == 5, "la carga es atomica: si algo falla antes de instalar, no cambia nada"
        assert dialogos.orden() == ["warning"] and dialogos.de("warning")[0]["titulo"] == "Seleccionar imagen" and "No se pudo leer la imagen" in dialogos.de("warning")[0]["texto"]

    def test_un_archivo_que_no_existe_se_dice_y_la_ventana_queda_igual(self, fabrica, dialogos, tmp_path, archivo_placa, clics):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        antes = huella(v)
        cargar(v, dialogos, str(tmp_path / "no_existe.png"))
        assert huella(v) == antes and v.estado == "analizada" and dialogos.orden() == ["warning"]

    def test_cargar_otra_imagen_descarta_los_puntos_y_el_sexto_clic_de_la_anterior(self, ventana, dialogos, archivo_placa, clics):
        cargar(ventana, dialogos, archivo_placa)
        marcar(ventana, clics[:2])
        assert len(ventana.marcas) == 2
        ventana.boton_sexto.click()
        clic(ventana, 87, 87)
        assert ventana.sexto_clic == (87.0, 87.0)
        cargar(ventana, dialogos, archivo_placa)
        assert ventana.estado == "imagen" and ventana.marcas == () and ventana.sexto_clic is None and not ventana.boton_sexto.isChecked() and ventana.modo_del_piso == "automatico", \
            "los puntos y el sexto clic son de la imagen anterior; sin el sexto clic el menu del piso vuelve al de omision"
        assert not por_gid(ventana.eje_imagen, "marca:clic") and ventana.etiqueta_marcas.isHidden()

    def test_una_carga_nueva_con_la_ventana_analizada_borra_el_analisis_viejo(self, fabrica, dialogos, archivo_placa, clics):
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        cargar(v, dialogos, archivo_placa)
        assert v.estado == "imagen" and not v.boton_guardar.isEnabled() and v.linea_regla.isHidden() and not v._fig_perfiles.axes and all(t.rowCount() == 0 for t in (v.tabla_perfiles, v.tabla_barridos))


@pytest.fixture
def pelicula_real():
    """`pelicula_real(clave)` da la ruta de una pelicula real del corpus (ImagenesDeReferencia/PlacasHistoricas, solo lectura), o salta con motivo (HI-0: sin corpus, skip honesto)."""
    def ruta(clave):
        r = _corpus.pelicula(clave)
        if r is None:
            pytest.skip(f"no esta la pelicula real {clave} en el corpus")
        return r
    return ruta


CLICS_ML0 = [(196, 143), (2542, 147), (1371, 1330), (2526, 2501), (171, 2480)]          # los clics del cuaderno del fisico sobre ML0 (R2, C.1)
CLICS_EPSON001 = [(178, 255), (2541, 252), (2553, 2593), (203, 2608), (1368, 1435)]     # UL, UR, DR, DL y el reticulo sobre EPSON001 (los de C.2)


class TestUnaPeliculaRealDelCorpus:
    def test_ml0_se_abre_se_marca_y_se_analiza_como_lo_mide_el_motor(self, fabrica, dialogos, pelicula_real):
        ruta = pelicula_real("ML0")
        v = analizada(fabrica(), dialogos, ruta, CLICS_ML0)
        resultado, _barrido, marcas = resultado_directo(Path(ruta).read_bytes(), CLICS_ML0)
        assert [m.como_dict() for m in v.marcas] == [m.como_dict() for m in marcas]
        for capa in (*CAPAS, "gris"):
            assert pm().valores_medidos(v._resultado, capa) == pm().valores_medidos(resultado, capa), capa
        linea = por_gid(v.eje_imagen, "recuadro")[0]
        assert list(zip(map(float, linea.get_xdata()), map(float, linea.get_ydata())))[:4] == [tuple(map(float, p)) for p in pm().recuadro_luminoso(v.marcas).esquinas]
        assert "JPEG" in v.etiqueta_imagen.text() and "8 bits por canal" in v.etiqueta_imagen.text()

    def test_un_tiff_con_canal_alfa_opaco_se_abre_y_no_cuenta_pixeles_transparentes(self, ventana, dialogos, pelicula_real):
        cargar(ventana, dialogos, pelicula_real("EPSON008_TIF"))
        assert ventana.estado == "imagen" and "TIFF, 8 bits por canal" in ventana.etiqueta_imagen.text() and "transparentes" not in ventana.etiqueta_imagen.text()

    def test_una_esquina_del_piso_tomada_con_el_respaldo_lo_rotula_en_la_imagen_y_en_las_capas(self, fabrica, dialogos, pelicula_real):
        """EPSON001 (A.3): su esquina inferior izquierda es dispersa y la reemplaza el giro +5 grados. Lo que se dibuja dice con que se tomo, sobre la ventana de 3 x 3 mm que se uso, en la imagen y en
        las tres capas (la sintetica no tiene ninguna esquina reemplazada: ahi la ausencia del rotulo es lo correcto)."""
        v = analizada(fabrica(), dialogos, pelicula_real("EPSON001_JPG"), CLICS_EPSON001)
        reemplazadas = [(e.esquina, e.origen) for e in v._resultado.piso.esquinas if e.estado == "reemplazada"]
        assert reemplazadas == [("DL", "giro +5 grados")], "premisa: solo la esquina inferior izquierda usa el respaldo"
        for ax in (v.eje_imagen, *v._fig_capas.axes[:3]):
            assert [(a.get_gid(), a.get_text()) for a in con_gid(ax, "piso:rotulo:")] == [("piso:rotulo:DL", "giro +5 grados")]
            assert len(por_gid(ax, "piso:caja:DL")) == 1


# ================================================================================================= 3. los clics

class TestLosClics:
    def test_cargar_varias_imagenes_seguidas_no_acumula_manejadores_de_clic(self, ventana, dialogos, archivo_placa, clics):
        """UN solo manejador de clics, conectado al construir la ventana: N imagenes seguidas acumularian N marcas por clic."""
        conexiones = lambda: len(ventana.lienzo_imagen.callbacks.callbacks.get("button_press_event", {}))
        antes = conexiones()
        for _ in range(3):
            cargar(ventana, dialogos, archivo_placa)
        assert conexiones() == antes
        clic(ventana, *clics[0])
        assert len(ventana.marcas) == 1, "un clic, una marca"

    def test_cada_clic_agrega_una_marca_y_el_quinto_analiza(self, ventana, dialogos, archivo_placa, clics):
        cargar(ventana, dialogos, archivo_placa)
        for i, c in enumerate(clics[:4], 1):
            clic(ventana, *c)
            assert len(ventana.marcas) == i and ventana.estado == "imagen" and not ventana.boton_guardar.isEnabled()
        clic(ventana, *clics[4])
        assert len(ventana.marcas) == 5 and ventana.estado == "analizada" and ventana.boton_guardar.isEnabled()

    def test_los_clics_se_guardan_a_tres_decimales_tal_como_se_marcaron(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        clic(ventana, 160.12345678, 134.98765432)
        assert ventana.marcas[0].clic == (160.123, 134.988), "los MouseEvent reales traen ruido de 1e-13 que no se guarda"

    def test_cada_marca_dice_cuantos_puntos_hay_y_cuales_se_refinaron(self, ventana, dialogos, archivo_placa, clics):
        cargar(ventana, dialogos, archivo_placa)
        clic(ventana, *clics[0])
        assert ventana.etiqueta_marcas.text().startswith("Marcas 1 de 5. Refinadas: 1; el punto se movió de ") and "mm del clic." in ventana.etiqueta_marcas.text()
        marcar(ventana, clics[1:])
        assert ventana.etiqueta_marcas.text().startswith("Marcas 5 de 5. Refinadas: 1, 2, 3, 4, 5; el punto se movió de ")

    def test_una_marca_sin_mancha_se_dice_sin_refinar_y_manda_el_clic(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        clic(ventana, 1300.0, 1900.0)                                  # sobre la meseta: sin tinta alrededor
        assert ventana.marcas[0].estado == "sin refinar" and ventana.marcas[0].punto == ventana.marcas[0].clic
        assert ventana.etiqueta_marcas.text().startswith("Marcas 1 de 5. Ninguna refinada.\nMarca 1: sin refinar: ")

    def test_el_orden_de_los_clics_no_importa(self, fabrica, dialogos, archivo_placa, clics, directo):
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        marcar(v, [clics[2], clics[4], clics[0], clics[3], clics[1]])         # el reticulo, una esquina, otra, otra, otra: otro orden
        assert v.estado == "analizada"
        esperado = {c: pm().valores_medidos(directo.resultado, c) for c in (*CAPAS, "gris")}
        assert {c: pm().valores_medidos(v._resultado, c) for c in (*CAPAS, "gris")} == esperado

    def test_el_quinto_clic_analiza_una_sola_vez_y_el_sexto_no_hace_nada(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        llamadas = []
        real = pm().analizar
        monkeypatch.setattr(pm(), "analizar", lambda *a, **k: llamadas.append(1) or real(*a, **k))
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        assert len(llamadas) == 1
        antes = huella(v)
        clic(v, 700, 900)
        assert len(llamadas) == 1 and len(v.marcas) == 5 and huella(v) == antes, "con los cinco puntos hechos un clic mas no marca ni vuelve a medir (para marcar otra vez: Recalcular)"

    @pytest.mark.parametrize("nombre,x,y,kwargs", [("fuera de la imagen por la derecha", 2800, 1000, {}), ("fuera por arriba", 1000, -40, {}), ("el boton derecho", 700, 900, {"boton": 3}),
                                                   ("el boton del medio", 700, 900, {"boton": 2}), ("un doble clic", 700, 900, {"doble": True})])
    def test_un_clic_que_no_cuenta_no_marca(self, ventana, dialogos, archivo_placa, nombre, x, y, kwargs):
        cargar(ventana, dialogos, archivo_placa)
        ventana.eje_imagen.set_xlim(-300, 3000)                      # el eje se ve mas grande que la imagen: se puede hacer clic fuera de ella
        ventana.eje_imagen.set_ylim(3000, -300)
        clic(ventana, x, y, **kwargs)
        assert ventana.marcas == (), nombre

    def test_marcar_un_punto_conserva_el_zoom_del_fisico(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        ventana.eje_imagen.set_xlim(100, 800)
        ventana.eje_imagen.set_ylim(900, 200)
        clic(ventana, 400, 500)
        assert len(ventana.marcas) == 1 and tuple(map(float, ventana.eje_imagen.get_xlim())) == (100.0, 800.0) and tuple(map(float, ventana.eje_imagen.get_ylim())) == (900.0, 200.0), \
            "dibujar la marca no devuelve la vista a la imagen entera"

    def test_una_marca_junto_al_borde_no_agranda_la_vista_de_la_imagen(self, ventana, dialogos, archivo_placa):
        """Sin zoom la vista es la imagen entera. El circulo de busqueda de una marca junto al borde se sale de la imagen: dibujarlo NO hace crecer la vista para alojarlo (el zoom de arriba usa `set_xlim`,
        que apaga el ajuste automatico y por eso no ve esta diferencia)."""
        cargar(ventana, dialogos, archivo_placa)
        ventana.lienzo_imagen.draw()
        antes = (tuple(map(float, ventana.eje_imagen.get_xlim())), tuple(map(float, ventana.eje_imagen.get_ylim())))
        clic(ventana, 12, 10)
        ventana.lienzo_imagen.draw()
        assert len(ventana.marcas) == 1
        assert (tuple(map(float, ventana.eje_imagen.get_xlim())), tuple(map(float, ventana.eje_imagen.get_ylim()))) == antes

    def test_una_marca_sobre_lo_transparente_se_refina_con_la_mascara_de_los_pixeles_con_dato(self, ventana, dialogos, tmp_path, clics):
        """Lo transparente no es tinta (A.1): la marca se refina con la mascara `Pelicula.validos`, como lo hace el servicio al guardar. Aqui la mancha de tinta del primer clic cae en una zona
        transparente que conserva su color oscuro: con la mascara la marca queda «sin refinar»; sin ella se refinaria sobre algo que no es pelicula (y la ventana y el guardado discreparian)."""
        imagen, _verdad = gen.generar_arreglo(bits=8, alfa=True, variante="A", seed=1)
        imagen = np.array(imagen)
        x, y = clics[0]
        imagen[int(y) - 60:int(y) + 60, int(x) - 60:int(x) + 60, 3] = 0
        datos = gen.codificar(imagen, "png", 600)
        ruta = tmp_path / "con_hueco.png"
        ruta.write_bytes(datos)
        pelicula, P = pel().leer_pelicula(datos), _P()
        punto = (round(float(x), 3), round(float(y), 3))
        con_mascara = pm().refinar_marca(pelicula.gris, punto, P, pel().escala_mm(pelicula.dpi, P), pelicula.validos)
        sin_mascara = pm().refinar_marca(pelicula.gris, punto, P, pel().escala_mm(pelicula.dpi, P))
        assert con_mascara.estado == "sin refinar" and sin_mascara.estado == "refinada", "premisa: aqui la mascara cambia la marca"
        cargar(ventana, dialogos, str(ruta))
        clic(ventana, x, y)
        assert ventana.marcas[0].como_dict() == con_mascara.como_dict()

    def test_antes_de_abrir_una_imagen_los_clics_no_hacen_nada(self, ventana):
        antes = huella(ventana)
        clic(ventana, 0.5, 0.5)
        assert ventana.marcas == () and huella(ventana) == antes

    @pytest.mark.parametrize("herramienta", ["zoom", "pan"])
    def test_con_la_lupa_o_el_desplazar_puestos_un_clic_no_marca(self, ventana, dialogos, archivo_placa, herramienta):
        cargar(ventana, dialogos, archivo_placa)
        getattr(ventana.barra_imagen, herramienta)()
        assert ventana.lienzo_imagen.widgetlock.locked()
        clic(ventana, 700, 900)
        assert ventana.marcas == (), "el clic de la lupa o del desplazar no es una marca"
        getattr(ventana.barra_imagen, herramienta)()
        clic(ventana, 700, 900)
        assert len(ventana.marcas) == 1, "apagada la herramienta, el clic vuelve a marcar"

    @pytest.mark.parametrize("herramienta, modo", [("zoom", "zoom rect"), ("pan", "pan/zoom")])
    def test_cargar_otra_imagen_recalcular_y_limpiar_apagan_la_lupa_y_el_desplazar_de_las_seis_figuras(self, fabrica, dialogos, archivo_placa, clics, herramienta, modo):
        """Con la lupa o el desplazar puestos los clics no marcan (la prueba de arriba): cada vez que la ventana cambia lo que se mira apaga TODAS las herramientas, las de la imagen y las de las cinco figuras."""
        acciones = {"cargar otra imagen": lambda v: cargar(v, dialogos, archivo_placa), "Recalcular": lambda v: v.boton_recalcular.click(), "Limpiar": lambda v: v.boton_limpiar.click()}
        for nombre, accion in acciones.items():
            v = analizada(fabrica(), dialogos, archivo_placa, clics)
            barras = [v.barra_imagen, v.barra_gris, v.barra_capas, v.barra_perfiles, v.barra_barridos, v.barra_cuadratura]
            for barra in barras:
                getattr(barra, herramienta)()
            assert all(barra.mode == modo for barra in barras), "premisa: la herramienta esta puesta en las seis"
            accion(v)
            assert [barra.mode == "" for barra in barras] == [True] * 6, nombre

    def test_un_trazo_ya_quitado_no_hace_caer_la_limpieza_de_lo_dibujado_sobre_la_imagen(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        quitado = ventana.eje_imagen.plot([10], [10], "x")[0]
        quitado.remove()
        ventana._artistas_de_la_imagen.append(quitado)
        ventana._quitar_artistas_de_la_imagen()                      # no lanza
        assert ventana._artistas_de_la_imagen == []

    def test_dibuja_cada_marca_con_su_numero_su_punto_y_su_circulo_de_busqueda(self, solo_lectura, directo, clics):
        ax = solo_lectura.v.eje_imagen
        cruces, puntos, circulos = por_gid(ax, "marca:clic"), por_gid(ax, "marca:punto"), por_gid(ax, "marca:circulo")
        assert len(cruces) == len(puntos) == len(circulos) == 5 and [t.get_text() for t in por_gid(ax, "marca:numero")] == ["1", "2", "3", "4", "5"]
        radio_px = _P()["radio_marca_mm"] / TAM
        for i, (c, p, o) in enumerate(zip(cruces, puntos, circulos)):
            assert (float(c.get_xdata()[0]), float(c.get_ydata()[0])) == pytest.approx(clics[i], abs=1e-3), "el clic tal como se marco"
            punto = directo.marcas[i].punto
            assert (float(p.get_xdata()[0]), float(p.get_ydata()[0])) == pytest.approx(punto, abs=1e-9), "el punto con que se mide es el que dio `refinar_marca`"
            assert (np.ptp(o.get_xdata()), np.ptp(o.get_ydata())) == pytest.approx((2 * radio_px, 2 * radio_px), abs=0.01), "el circulo de busqueda es de `radio_marca_mm`"


# ================================================================================================= 4. «Marcar pelicula sin irradiar»: el sexto clic

class TestElSextoClic:
    def test_el_clic_siguiente_es_el_sexto_y_nunca_un_punto_del_campo(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        llamadas = []
        real = pm().clasificar_puntos
        monkeypatch.setattr(pm(), "clasificar_puntos", lambda puntos, *a, **k: llamadas.append([tuple(map(float, getattr(p, "clic", p))) for p in puntos]) or real(puntos, *a, **k))
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        marcar(v, clics[:2])
        v.boton_sexto.click()
        assert v.boton_sexto.isChecked()
        clic(v, 87, 87)
        assert v.sexto_clic == (87.0, 87.0) and len(v.marcas) == 2 and not v.boton_sexto.isChecked(), "el sexto no es una marca: las dos de antes siguen siendo dos y el boton se desarma"
        marcar(v, clics[2:])
        assert v.estado == "analizada" and len(v.marcas) == 5 and llamadas
        assert all(len(l) == 5 and (87.0, 87.0) not in l for l in llamadas), "a `clasificar_puntos` solo llegan los cinco puntos del campo"

    def test_pone_el_menu_del_piso_en_punto_marcado_y_dibuja_su_cuadrado_de_3_mm(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        assert not ventana.selector_piso.model().item(1).isEnabled(), "sin el sexto clic el piso «punto marcado» no se ofrece"
        ventana.boton_sexto.click()
        clic(ventana, 87, 87)
        assert ventana.modo_del_piso == "punto_manual" and ventana.selector_piso.model().item(1).isEnabled()
        cuadrado, cruz = por_gid(ventana.eje_imagen, "sexto:cuadrado")[0], por_gid(ventana.eje_imagen, "sexto:clic")[0]
        lado_px = _P()["lado_punto_manual_mm"] / TAM
        assert _P()["lado_punto_manual_mm"] == 3.0
        assert (np.ptp(cuadrado.get_xdata()), np.ptp(cuadrado.get_ydata())) == pytest.approx((lado_px, lado_px), abs=1e-6)
        assert (float(cruz.get_xdata()[0]), float(cruz.get_ydata()[0])) == (87.0, 87.0)
        assert cuadrado.get_xdata()[0] == pytest.approx(87.0 - lado_px / 2)

    def test_con_los_cinco_puntos_hechos_vuelve_a_medir_con_el_punto_marcado(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        llamadas = []
        real = pm().analizar
        monkeypatch.setattr(pm(), "analizar", lambda *a, **k: llamadas.append(k) or real(*a, **k))
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        assert llamadas[0]["modo_piso"] == "automatico" and llamadas[0]["punto_manual"] is None
        v.boton_sexto.click()
        clic(v, 87, 87)
        assert len(llamadas) == 2 and llamadas[1]["modo_piso"] == "punto_manual" and llamadas[1]["punto_manual"] == (87.0, 87.0)
        assert v.estado == "analizada" and v._resultado.piso.modo == "punto_manual" and v._resultado.piso.origen == "manual"
        assert "punto marcado" in v.etiqueta_piso.text() and por_gid(v.eje_imagen, "piso:caja:punto"), "el cuadrado del piso se ve en la imagen"
        assert not por_gid(v.eje_imagen, "piso:caja:UL"), "con el punto marcado no hay esquinas"

    def test_volver_al_piso_automatico_despues_del_sexto_clic_mide_sin_el_punto_ni_la_referencia(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        llamadas = []
        real = pm().analizar
        monkeypatch.setattr(pm(), "analizar", lambda *a, **k: llamadas.append(k) or real(*a, **k))
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        v.boton_sexto.click()
        clic(v, 87, 87)
        elegir_piso(v, "automatico")
        assert v.estado == "analizada" and len(llamadas) == 3 and not dialogos.llamadas
        assert llamadas[2]["modo_piso"] == "automatico" and llamadas[2]["punto_manual"] is None and llamadas[2]["referencia_virgen"] is None
        assert v.sexto_clic == (87.0, 87.0) and v._resultado.piso.modo == "automatico", "el sexto clic sigue hecho (se puede volver a elegir) pero no se usa en el modo automatico"

    def test_antes_de_los_cinco_puntos_el_sexto_se_guarda_para_cuando_se_completen(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        llamadas = []
        real = pm().analizar
        monkeypatch.setattr(pm(), "analizar", lambda *a, **k: llamadas.append(k) or real(*a, **k))
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        v.boton_sexto.click()
        clic(v, 87, 87)
        assert not llamadas and v.estado == "imagen"
        marcar(v, clics)
        assert len(llamadas) == 1 and llamadas[0]["modo_piso"] == "punto_manual" and llamadas[0]["punto_manual"] == (87.0, 87.0)

    def test_pulsar_el_boton_otra_vez_lo_desarma_y_el_clic_siguiente_es_un_punto_normal(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        ventana.boton_sexto.click()
        assert ventana.boton_sexto.isChecked(), "el boton es de dos estados: el primer clic lo arma"
        ventana.boton_sexto.click()
        assert not ventana.boton_sexto.isChecked()
        clic(ventana, 160, 134)
        assert len(ventana.marcas) == 1 and ventana.sexto_clic is None

    def test_un_sexto_clic_fuera_de_la_imagen_no_cuenta_y_el_boton_sigue_armado(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        ventana.eje_imagen.set_xlim(-300, 3000)
        ventana.boton_sexto.click()
        clic(ventana, -100, 500)
        assert ventana.sexto_clic is None and ventana.boton_sexto.isChecked()

    def test_sin_imagen_el_boton_se_desarma_solo(self, ventana):
        ventana.boton_sexto.click()
        assert not ventana.boton_sexto.isChecked() and ventana.sexto_clic is None

    def test_el_sexto_clic_se_dibuja_aunque_aun_no_haya_analisis(self, ventana, dialogos, archivo_placa):
        cargar(ventana, dialogos, archivo_placa)
        ventana.boton_sexto.click()
        clic(ventana, 87, 87)
        assert por_gid(ventana.eje_imagen, "sexto:cuadrado") and "punto sin irradiar (sexto clic)" in etiquetas(ventana.eje_imagen.get_legend() and ventana.eje_imagen)


# ================================================================================================= 5. el analisis es el del motor

class TestElAnalisisEsElDelMotor:
    def test_los_valores_de_cada_capa_son_los_del_motor_sobre_esos_bytes(self, solo_lectura, oraculos):
        v = solo_lectura.v
        esperado = oraculos["automatico"]
        assert v._resultado.estado == esperado.estado == "ok" and v._resultado.version == esperado.version
        for capa in (*CAPAS, "gris"):
            assert pm().valores_medidos(v._resultado, capa) == esperado.valores[capa], capa

    def test_el_piso_es_el_del_motor_y_se_toma_en_el_modo_por_omision(self, solo_lectura, oraculos):
        piso = solo_lectura.v._resultado.piso
        assert piso.modo == "automatico" and piso.como_dict() == oraculos["automatico"].piso

    def test_se_mide_con_los_40_parametros_de_fabrica_enteros(self, solo_lectura):
        assert solo_lectura.v._resultado.parametros == _P() and len(_P()) == len(pm().VALORES_DE_LA_GEOMETRIA) == 42      # OD.1: eran 40; la base de la medida es el 41. CD.6 (31-10): el 42 es `diferencia_virgen_maxima_pct` (`PARAMETROS_DE_LA_DOSIS`)

    def test_la_pelicula_no_se_retiene_tras_el_analisis(self, solo_lectura):
        v = solo_lectura.v
        assert v._pelicula is None, "una pagina del escaner son 540 MB leidos en flotante: el resultado ya trae la pelicula girada y recortada"
        assert v._resultado.girada.capas["gris"].shape[0] <= 1.05 * 2734, "la pelicula girada es la RECORTADA a la pelicula (con su margen), nunca una pagina entera"

    def test_las_marcas_que_la_ventana_guarda_son_las_refinadas_del_motor(self, solo_lectura, directo):
        assert [m.como_dict() for m in solo_lectura.v.marcas] == [m.como_dict() for m in directo.marcas]

    def test_el_barrido_es_el_del_motor(self, solo_lectura, directo):
        assert solo_lectura.v._barrido.como_dict() == directo.barrido.como_dict()

    def test_ningun_control_cambia_los_parametros_del_analisis(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        recibidos = []
        real = pm().analizar
        monkeypatch.setattr(pm(), "analizar", lambda pelicula, puntos, parametros, *a, **k: recibidos.append(copy.deepcopy(parametros)) or real(pelicula, puntos, parametros, *a, **k))
        v = analizada(fabrica(), dialogos, archivo_placa, clics)
        elegir_capa(v, "B")
        v.boton_sexto.click()
        clic(v, 87, 87)
        assert len(recibidos) == 2 and all(p == _P() for p in recibidos), "ni la capa, ni el piso, ni el sexto clic, ni nada de la ventana cambian un parametro (PD1)"


# ================================================================================================= 6. cada pestana dibuja lo que dice

class TestPestana1Imagen:
    def test_el_recuadro_es_el_de_recuadro_luminoso_con_los_cinco_puntos(self, solo_lectura, directo):
        v = solo_lectura.v
        recuadro = pm().recuadro_luminoso(v.marcas)
        linea = por_gid(v.eje_imagen, "recuadro")[0]
        esperado = [tuple(map(float, p)) for p in recuadro.esquinas] + [tuple(map(float, recuadro.esquinas[0]))]
        assert list(zip(map(float, linea.get_xdata()), map(float, linea.get_ydata()))) == esperado, "los vertices son los de `recuadro_luminoso`, los mismos que imprime el PDF"
        independiente = [tuple(map(float, m.punto)) for m in (directo.marcas[0], directo.marcas[1], directo.marcas[3], directo.marcas[4])]
        assert esperado[:4] == independiente, "y son los cuatro puntos refinados de las esquinas (UL, UR, DR, DL): el reticulo no es una esquina"

    def test_las_diagonales_el_cruce_y_el_reticulo_son_los_de_la_geometria(self, solo_lectura, directo):
        ax = solo_lectura.v.eje_imagen
        g = directo.resultado.geometria
        diagonales = por_gid(ax, "diagonal")
        assert len(diagonales) == 2
        ul, ur, dr, dl = (tuple(map(float, p)) for p in g.esquinas)
        pares = sorted((tuple(zip(map(float, d.get_xdata()), map(float, d.get_ydata()))) for d in diagonales))
        assert pares == sorted([(ul, dr), (ur, dl)])
        cruce, reticulo = por_gid(ax, "cruce"), por_gid(ax, "reticulo")
        assert len(cruce) == len(reticulo) == 1
        assert (float(cruce[0].get_xdata()[0]), float(cruce[0].get_ydata()[0])) == pytest.approx(tuple(map(float, g.cruce)), abs=1e-9)
        assert (float(reticulo[0].get_xdata()[0]), float(reticulo[0].get_ydata()[0])) == pytest.approx(tuple(map(float, g.reticulo)), abs=1e-9)

    def test_las_dos_bandas_de_1_mm_de_los_perfiles_contienen_el_cruce_y_miden_1_mm_de_ancho(self, solo_lectura, directo):
        ax = solo_lectura.v.eje_imagen
        g, girada = directo.resultado.geometria, directo.resultado.girada
        alto, ancho = girada.capas["gris"].shape
        for eje in ("crossplane", "inplane"):
            banda = por_gid(ax, f"banda:{eje}")
            assert len(banda) == 1, eje
            xy = np.asarray(banda[0].get_xy())
            assert RutaMpl(xy).contains_point(tuple(map(float, g.cruce))), f"la banda {eje} pasa por el cruce de diagonales"
            ancho_x, ancho_y = np.ptp(xy[:, 0]), np.ptp(xy[:, 1])
            corto, largo = (ancho_y, ancho_x) if eje == "crossplane" else (ancho_x, ancho_y)
            assert corto == pytest.approx(_P()["banda_perfil_mm"] / TAM, abs=1.5), f"la banda {eje} mide banda_perfil_mm de ancho"
            assert largo == pytest.approx(ancho if eje == "crossplane" else alto, abs=1.5), f"y recorre la pelicula entera a lo largo del eje {eje}"

    def test_la_zona_central_de_la_meseta_y_del_barrido_es_la_del_motor(self, solo_lectura, directo):
        zona = por_gid(solo_lectura.v.eje_imagen, "zona")
        assert len(zona) == 1
        xy = np.asarray(zona[0].get_xy())
        (x0, x1), (y0, y1) = directo.barrido.ejes["inplane"].zona_px, directo.barrido.ejes["crossplane"].zona_px
        assert (xy[:, 0].min(), xy[:, 0].max()) == pytest.approx((x0, x1), abs=1.5) and (xy[:, 1].min(), xy[:, 1].max()) == pytest.approx((y0, y1), abs=1.5)
        luz = directo.resultado.bordes_luz_px
        medio_ancho = _P()["fraccion_meseta"] / 2 * (luz["crossplane"][1] - luz["crossplane"][0])
        assert (x1 - x0) / 2 == pytest.approx(medio_ancho, abs=1.0), "la zona central mide la fraccion de la meseta entre los bordes luminosos"

    def test_la_region_del_piso_son_los_pixeles_que_se_usaron_y_la_caja_de_cada_esquina(self, solo_lectura, directo):
        ax = solo_lectura.v.eje_imagen
        region = directo.resultado.piso.region
        imagen = por_gid(ax, "piso:pixeles")
        assert len(imagen) == 1
        rgba = np.asarray(imagen[0].get_array())
        assert rgba.dtype == np.uint8 and rgba.shape == region.mascara.shape + (4,) and int((rgba[:, :, 3] > 0).sum()) == int(region.mascara.sum())
        x0, y0, x1, y1 = region.caja
        assert tuple(map(float, imagen[0].get_extent())) == (x0 - 0.5, x1 - 0.5, y1 - 0.5, y0 - 0.5)
        usadas = [e.esquina for e in directo.resultado.piso.esquinas if e.estado in ("ok", "reemplazada")]
        assert usadas == ["UL", "UR", "DR", "DL"] and all(len(por_gid(ax, f"piso:caja:{e}")) == 1 for e in usadas)
        assert not con_gid(ax, "piso:rotulo:"), "ninguna esquina se tomo con un respaldo: ningun rotulo de «giro»"

    def test_la_leyenda_dice_cada_cosa_que_se_dibuja(self, solo_lectura):
        etiquetas_vistas = [_normalizar_texto(e) for e in etiquetas(solo_lectura.v.eje_imagen)]
        for esperada in ("clic", "punto refinado", "círculo de búsqueda", "recuadro del campo luminoso", "diagonales", "cruce de diagonales (centro luminoso)", "retículo", "banda del perfil (1 mm)",
                         "zona central de la meseta y del barrido", "región del piso"):
            assert esperada in etiquetas_vistas, (esperada, etiquetas_vistas)

    def test_al_lado_van_los_dos_perfiles_del_gris_con_el_fwhm_del_motor(self, solo_lectura, oraculos):
        v = solo_lectura.v
        assert len(v._fig_gris.axes) == 2
        gris = oraculos["automatico"].valores["gris"]
        assert [e.get_title() for e in v._fig_gris.axes] == [f"Gris, crossplane: FWHM {gris['fwhm_crossplane_mm']:.3f} mm", f"Gris, inplane: FWHM {gris['fwhm_inplane_mm']:.3f} mm"]

    def test_los_perfiles_del_gris_llevan_todas_las_lineas_de_la_pestana_3(self, solo_lectura):
        gids = {"perfil:crudo", "perfil:suavizado", "perfil:piso", "perfil:meseta", "perfil:altura_media", "perfil:penumbra_alta", "perfil:penumbra_baja", "perfil:zona", "perfil:exclusion",
                "perfil:borde_luz", "perfil:borde_rad", "perfil:cruce"}
        for ax in solo_lectura.v._fig_gris.axes:
            assert gids <= {a.get_gid() for a in ax.get_children()}

    def test_la_tabla_de_desfases_es_la_del_gris_con_los_numeros_del_motor(self, solo_lectura, directo):
        gris = directo.resultado.capas["gris"]
        c = gris.coincidencia_mm

        def f(x):
            return f"{x:+.3f}"
        esperado = [["Lado izquierdo (radiación − luz) [mm]", f(c["izquierdo"])], ["Lado derecho (radiación − luz) [mm]", f(c["derecho"])], ["Lado superior (radiación − luz) [mm]", f(c["superior"])],
                    ["Lado inferior (radiación − luz) [mm]", f(c["inferior"])],
                    ["Radiación − cruce de diagonales (x; y) [mm]", f"{f(gris.radiacion_menos_luz_mm[0])}; {f(gris.radiacion_menos_luz_mm[1])}"],
                    ["Luz − retículo (x; y) [mm]", f"{f(directo.resultado.luz_menos_reticulo_mm[0])}; {f(directo.resultado.luz_menos_reticulo_mm[1])}"],
                    ["Radiación − retículo (x; y) [mm]", f"{f(gris.radiacion_menos_reticulo_mm[0])}; {f(gris.radiacion_menos_reticulo_mm[1])}"]]
        assert texto_de_la_tabla(solo_lectura.v.tabla_desfases) == esperado

    def test_la_nota_dice_que_lo_que_se_guarda_es_lo_de_la_capa_reportada(self, solo_lectura):
        assert solo_lectura.v.nota_pestana1.text() == "Estos son los desfases del perfil de grises. Lo que se guarda y se imprime es lo de la capa verde, que se ve en la pestaña 3."

    def test_los_ejes_de_la_imagen_tienen_su_rotulo_en_pixeles_con_corchetes(self, solo_lectura):
        ax = solo_lectura.v.eje_imagen
        assert (ax.get_xlabel(), ax.get_ylabel()) == ("columna de la imagen [px]", "fila de la imagen [px]")


class TestPestana2Capas:
    def test_hay_tres_capas_y_tres_barras_de_color(self, solo_lectura):
        f = solo_lectura.v._fig_capas
        assert len(f.axes) == 6
        assert [e.get_title().split(":")[0] for e in f.axes[:3]] == ["Capa roja", "Capa verde", "Capa azul"]
        # CD.1 (23-10, clase b; pedido del fisico: «dejé de normalizar la imagen, para crear un rango absoluto»): la barra ya no es la normalizada de 0 a 1 sino la unidad de la base del analisis. Esta ventana mide
        # en valor de pixel (el fixture de E.1), asi que dice «valor de píxel [nivel]» y va de 0 a 255; la netOD la fijan `test_cd1_capas_en_unidades_absolutas.py` y `test_od1_densidad_optica.py`.
        assert [e.get_label() for e in f.axes[3:]] == ["<colorbar>"] * 3 and all(e.get_xlabel() == "valor de píxel [nivel]" and tuple(e.get_xlim()) == (0.0, 255.0) for e in f.axes[3:])

    @pytest.mark.parametrize("k,capa", [(0, "R"), (1, "G"), (2, "B")])
    def test_cada_capa_se_pinta_en_su_unidad_y_en_jet_uint8(self, solo_lectura, directo, k, capa):
        # CD.1 (23-10, clase b): antes se pintaba normalizada entre el piso y la meseta; ahora se pinta en la unidad de la base de este analisis (valor de pixel: los niveles, de 0 a 255) con NaN fuera de la pelicula.
        r = directo.resultado
        imagen = por_gid(solo_lectura.v._fig_capas.axes[k], "capas:imagen")[0]
        arreglo = np.asarray(imagen.get_array())
        assert arreglo.dtype == np.uint8 and arreglo.shape == r.girada.capas[capa].shape + (4,), "RGBA uint8 con el mapa de color ya aplicado: una imagen 2D con mapa de color pedia 2 GB"
        niveles = np.array(r.girada.capas[capa], dtype=np.float32)
        niveles[~r.girada.validos] = np.nan
        assert np.array_equal(arreglo, dibujo_mod().colorear(niveles / np.float32(255.0)))
        assert imagen.get_interpolation() == "nearest"
        ox, oy = r.girada.origen
        alto, ancho = niveles.shape
        assert tuple(map(float, imagen.get_extent())) == (ox - 0.5, ox + ancho - 0.5, oy + alto - 0.5, oy - 0.5)

    @pytest.mark.parametrize("k,capa", [(0, "R"), (1, "G"), (2, "B")])
    def test_el_titulo_dice_la_escala_el_piso_y_la_meseta(self, solo_lectura, directo, k, capa):
        m = directo.resultado.capas[capa]
        meseta = float(np.mean([m.crossplane.meseta, m.inplane.meseta]))
        # CD.1 (23-10, clase b): el titulo ya no dice que el cero es el piso y el uno la meseta (ni la base, que OD.1 le sumaba): dice la escala de la capa, su piso y su meseta en niveles, partido en renglones de 52 caracteres.
        esperado = f"Capa {ADJETIVO[capa]}: valor de píxel de 0 a 255 [nivel]; piso {m.piso:.1f} y meseta {meseta:.1f} [nivel]"
        assert solo_lectura.v._fig_capas.axes[k].get_title() == textwrap.fill(esperado.replace(" [", "\u00a0["), 52)      # CD1-M4: el espacio antes de cada unidad (« [nivel]») es de no separacion

    def test_la_cruz_punteada_blanca_pasa_por_el_cruce_de_diagonales_y_hay_cuadricula(self, solo_lectura, directo):
        cx, cy = directo.resultado.girada.cruce
        for ax in solo_lectura.v._fig_capas.axes[:3]:
            vertical, horizontal = por_gid(ax, "capas:cruz_vertical")[0], por_gid(ax, "capas:cruz_horizontal")[0]
            assert float(vertical.get_xdata()[0]) == pytest.approx(cx) and float(horizontal.get_ydata()[0]) == pytest.approx(cy)
            assert vertical.get_color() == "white" and vertical.get_linestyle() == ":" and ax.xaxis.get_gridlines()[0].get_visible()

    def test_el_recuadro_va_en_el_marco_girado_y_la_region_del_piso_solo_como_cajas(self, solo_lectura, directo):
        g = directo.resultado.geometria
        for ax in solo_lectura.v._fig_capas.axes[:3]:
            linea = por_gid(ax, "recuadro")[0]
            esperado = [tuple(map(float, p)) for p in g.esquinas_giradas] + [tuple(map(float, g.esquinas_giradas[0]))]
            assert list(zip(map(float, linea.get_xdata()), map(float, linea.get_ydata()))) == esperado
            assert all(len(por_gid(ax, f"piso:caja:{e}")) == 1 for e in ("UL", "UR", "DR", "DL")) and not por_gid(ax, "piso:pixeles"), "la mascara exacta solo se dibuja en la pestana 1"

    def test_los_ejes_de_las_capas_cubren_la_pelicula_girada_entera(self, solo_lectura, directo):
        ox, oy = directo.resultado.girada.origen
        alto, ancho = directo.resultado.girada.capas["gris"].shape
        for ax in solo_lectura.v._fig_capas.axes[:3]:
            assert tuple(map(float, ax.get_xlim())) == (ox - 0.5, ox + ancho - 0.5) and tuple(map(float, ax.get_ylim())) == (oy + alto - 0.5, oy - 0.5)


class TestPestana3PerfilesPorCapa:
    def test_son_ocho_perfiles_cada_uno_con_el_fwhm_del_motor_en_su_titulo(self, solo_lectura, oraculos):
        valores = oraculos["automatico"].valores
        for (capa, eje), ax in _grupo(solo_lectura.v).items():
            nombre = "Gris" if capa == "gris" else f"Capa {ADJETIVO[capa]}" + (" (reportada)" if capa == "G" else "")
            assert ax.get_title() == f"{nombre}, {eje}: FWHM {valores[capa]['fwhm_' + eje + '_mm']:.3f} mm", (capa, eje)

    def test_cada_perfil_dibuja_todo_lo_que_se_uso_para_medirlo(self, solo_lectura):
        completos = {"perfil:crudo": 1, "perfil:suavizado": 1, "perfil:piso": 1, "perfil:meseta": 1, "perfil:altura_media": 1, "perfil:penumbra_alta": 1, "perfil:penumbra_baja": 1, "perfil:zona": 2,
                     "perfil:exclusion": 2, "perfil:borde_luz": 2, "perfil:borde_rad": 2, "perfil:cruce": 1}
        for clave, ax in _grupo(solo_lectura.v).items():
            vistos = {}
            for a in ax.get_children():
                if (a.get_gid() or "").startswith("perfil:"):
                    vistos[a.get_gid()] = vistos.get(a.get_gid(), 0) + 1
            assert vistos == completos, (clave, vistos)

    def test_las_curvas_del_perfil_y_su_suavizado_son_las_del_motor(self, solo_lectura, directo):
        """Que haya un trazo con el nombre no basta: sus datos son el perfil de la banda (promedio de 1 mm) y el suavizado con que se buscaron los cruces, en mm desde el cruce de diagonales."""
        for (capa, eje), ax in _grupo(solo_lectura.v).items():
            m = getattr(directo.resultado.capas[capa], eje)
            x = (m.perfil.desde_px + np.arange(len(m.perfil.valores)) - m.centro_px) * m.tam_mm
            for gid, y in (("perfil:crudo", m.perfil.valores), ("perfil:suavizado", m.suavizado)):
                linea = por_gid(ax, gid)[0]
                assert np.isfinite(y).sum() > 1000, "compuerta: hay perfil de verdad que comparar"
                assert np.allclose(linea.get_xdata(), x, equal_nan=True) and np.allclose(linea.get_ydata(), y, equal_nan=True), (capa, eje, gid)      # NaN: fuera de la pelicula

    def test_los_niveles_dibujados_son_los_del_motor(self, solo_lectura, directo):
        for (capa, eje), ax in _grupo(solo_lectura.v).items():
            m = getattr(directo.resultado.capas[capa], eje)
            nivel = {g: float(por_gid(ax, g)[0].get_ydata()[0]) for g in ("perfil:piso", "perfil:meseta", "perfil:altura_media", "perfil:penumbra_alta", "perfil:penumbra_baja")}
            assert nivel["perfil:piso"] == pytest.approx(m.piso) and nivel["perfil:meseta"] == pytest.approx(m.meseta)
            contraste = m.piso - m.meseta
            assert nivel["perfil:altura_media"] == pytest.approx(m.piso - _P()["altura_media"] * contraste), "la altura media: el 50 % entre el piso y la meseta"
            assert nivel["perfil:penumbra_alta"] == pytest.approx(m.piso - _P()["penumbra_alta"] * contraste)
            assert nivel["perfil:penumbra_baja"] == pytest.approx(m.piso - _P()["penumbra_baja"] * contraste)

    def test_el_eje_x_son_milimetros_desde_el_cruce_y_cubre_la_pelicula_a_los_dos_lados_del_campo(self, solo_lectura, directo):
        for (capa, eje), ax in _grupo(solo_lectura.v).items():
            m = getattr(directo.resultado.capas[capa], eje)
            x0, x1 = ax.get_xlim()
            assert x0 == pytest.approx((m.perfil.desde_px - m.centro_px) * m.tam_mm) and x1 == pytest.approx((m.perfil.desde_px + len(m.perfil.valores) - 1 - m.centro_px) * m.tam_mm)
            assert x0 < -55.0 and x1 > 55.0, f"{capa} {eje}: la pelicula de {x0:.1f} a {x1:.1f} mm cubre los bordes del campo (a +-50 mm) con margen a cada lado"
            assert ax.get_xlabel() == ("posición desde el cruce de diagonales [mm]" if capa == "gris" else "") and ax.get_ylabel() == "valor de píxel [nivel]"

    def test_los_bordes_de_radiacion_dibujados_dan_el_fwhm_y_los_luminosos_son_los_de_esa_linea(self, solo_lectura, directo, oraculos):
        for (capa, eje), ax in _grupo(solo_lectura.v).items():
            m = getattr(directo.resultado.capas[capa], eje)
            radiacion = sorted(float(a.get_xdata()[0]) for a in por_gid(ax, "perfil:borde_rad"))
            assert radiacion == pytest.approx(sorted(float((b - m.centro_px) * m.tam_mm) for b in m.bordes_rad_px))
            assert radiacion[1] - radiacion[0] == pytest.approx(oraculos["automatico"].valores[capa]["fwhm_" + eje + "_mm"], abs=1e-9)
            luz = sorted(float(a.get_xdata()[0]) for a in por_gid(ax, "perfil:borde_luz"))
            assert luz == pytest.approx(sorted(float((b - m.centro_px) * m.tam_mm) for b in m.bordes_luz_px))

    def test_la_exclusion_del_reticulo_y_la_zona_central_estan_a_lo_que_dicen_los_parametros(self, solo_lectura, directo):
        for (capa, eje), ax in _grupo(solo_lectura.v).items():
            m = getattr(directo.resultado.capas[capa], eje)
            excl = sorted(float(a.get_xdata()[0]) for a in por_gid(ax, "perfil:exclusion"))
            reticulo_mm = (np.mean(excl))
            assert excl[1] - excl[0] == pytest.approx(2 * _P()["excepcion_centro_mm"], abs=1e-6), (capa, eje)
            assert abs(reticulo_mm) < 1.5, "la exclusion esta centrada en el reticulo, que esta cerca del cruce de diagonales"
            assert excl == pytest.approx(sorted(float((b - m.centro_px) * m.tam_mm) for b in m.exclusion_px)), (capa, eje, "los limites que dibuja son los del motor, no otros a la misma distancia del reticulo")
            zona = sorted(float(a.get_xdata()[0]) for a in por_gid(ax, "perfil:zona"))
            assert zona == pytest.approx(sorted(float((b - m.centro_px) * m.tam_mm) for b in m.zona_px))

    def test_la_leyenda_es_una_para_toda_la_figura_y_dice_cada_trazo(self, solo_lectura):
        figura = solo_lectura.v._fig_perfiles
        assert len(figura.legends) == 1 and figura.legends[0].get_gid() == "leyenda"
        textos = [_normalizar_texto(t.get_text()) for t in figura.legends[0].get_texts()]
        for esperado in ("perfil, promedio de la banda", "piso", "media de la meseta", "bordes de radiación", "bordes luminosos de esta línea", "cruce de diagonales", "exclusión del retículo",
                         "límites de la zona central de la meseta"):
            assert esperado in textos, (esperado, textos)

    def test_la_tabla_tiene_una_fila_por_capa_y_eje_con_los_numeros_del_motor(self, solo_lectura, directo, oraculos):
        t = solo_lectura.v.tabla_perfiles
        assert [t.horizontalHeaderItem(c).text() for c in range(t.columnCount())] == list(dibujo_mod().COLUMNAS_DE_LOS_PERFILES)
        filas = texto_de_la_tabla(t)
        assert [(f[0], f[1]) for f in filas] == [(n, e) for n in ("Capa roja", "Capa verde", "Capa azul", "Gris") for e in ("crossplane", "inplane")]
        valores = oraculos["automatico"].valores
        for fila, ((capa, eje), _ax) in zip(filas, _grupo(solo_lectura.v).items()):
            m = getattr(directo.resultado.capas[capa], eje)
            assert fila[2] == "ok" and fila[3] == f"{valores[capa]['fwhm_' + eje + '_mm']:.3f}"
            lados = ("izquierdo", "derecho") if eje == "crossplane" else ("superior", "inferior")
            assert fila[4] == f"{directo.resultado.capas[capa].coincidencia_mm[lados[0]]:+.3f}" and fila[5] == f"{directo.resultado.capas[capa].coincidencia_mm[lados[1]]:+.3f}"
            assert fila[6] == f"{m.penumbras_mm[0]:.3f}" and fila[7] == f"{m.penumbras_mm[1]:.3f}" and fila[8] == f"{m.piso:.1f}" and fila[9] == f"{m.meseta:.1f}"

    def test_solo_la_fila_de_la_capa_reportada_dice_se_guarda_y_las_capas_no_se_comparan(self, solo_lectura):
        tabla = solo_lectura.v.tabla_perfiles
        cabeceras = [tabla.horizontalHeaderItem(c).text() for c in range(tabla.columnCount())]
        assert cabeceras == ["Capa", "Eje", "Estado", "FWHM [mm]", "Desfase izquierdo o superior [mm]", "Desfase derecho o inferior [mm]", "Penumbra izquierda o superior [mm]",
                             "Penumbra derecha o inferior [mm]", "Piso [nivel]", "Meseta [nivel]", "Avisos", "Se guarda"], "las columnas del plan (las escribe la prueba a mano), ninguna que compare capas"
        filas = texto_de_la_tabla(tabla)
        assert all(len(f) == 12 and None not in f for f in filas)
        assert [f[11] for f in filas] == ["", "", "se guarda", "se guarda", "", "", "", ""], "la capa verde, y nada mas"
        palabras = re.compile(r"mayor|menor|mejor|peor|compar|diferencia|promedio de las capas|cumple|tolerancia", re.I)
        assert not [t for f in [cabeceras, *filas] for t in f if palabras.search(t)], "PD3: cada capa por separado, sin ninguna marca ni juicio que las compare"

    def test_la_linea_del_piso_va_una_sola_vez_sobre_las_pestanas_con_lo_que_midio_el_motor(self, solo_lectura, directo):
        piso = directo.resultado.piso
        distancia = piso.region.distancia_media_mm
        esperado = f"Piso (capa verde): {piso.capas['G'].mediana:.0f} niveles; automático, en las cuatro esquinas de la película a {distancia:.1f} mm del campo."
        # OD.1 (21-10): la linea empieza por la frase de la base con que se midio, y tras ella viene la del piso de siempre.
        esperado_completo = dibujo_mod().texto_de_la_base(directo.resultado.base) + " " + esperado
        assert solo_lectura.v.etiqueta_piso.text() == esperado_completo
        assert [w.text() for w in recorrer(solo_lectura.v) if isinstance(w, QLabel) and "Piso (capa" in w.text()] == [esperado_completo], "la distancia del piso al campo se dice UNA vez, no en cada pestana"


class TestPestana4Barridos:
    def test_hay_un_grafico_por_eje_con_las_cuatro_capas_y_todas_las_bandas(self, solo_lectura, directo):
        ejes = solo_lectura.v._fig_barridos.axes
        assert len(ejes) == 2 and [e.get_title() for e in ejes] == ["Barrido crossplane: FWHM de cada banda de 1.0 mm", "Barrido inplane: FWHM de cada banda de 1.0 mm"]
        for ax, eje in zip(ejes, ("crossplane", "inplane")):
            for capa in (*CAPAS, "gris"):
                b = directo.barrido.ejes[eje].capas[capa]
                linea = por_gid(ax, f"barrido:bandas:{capa}")[0]
                assert len(linea.get_xdata()) == len(b.bandas) == 79, "todas las bandas, sin descartar ninguna"
                assert list(map(float, linea.get_xdata())) == [x.posicion_mm for x in b.bandas] and list(map(float, linea.get_ydata())) == pytest.approx([x.fwhm_mm for x in b.bandas])

    def test_la_media_la_mediana_el_corte_central_y_los_limites_de_la_zona_son_los_del_motor(self, solo_lectura, directo):
        for ax, eje in zip(solo_lectura.v._fig_barridos.axes, ("crossplane", "inplane")):
            b = directo.barrido.ejes[eje]
            for capa in (*CAPAS, "gris"):
                c = b.capas[capa]
                assert float(por_gid(ax, f"barrido:media:{capa}")[0].get_ydata()[0]) == pytest.approx(c.estadistica.media_mm)
                assert float(por_gid(ax, f"barrido:mediana:{capa}")[0].get_ydata()[0]) == pytest.approx(c.estadistica.mediana_mm)
                central = por_gid(ax, f"barrido:central:{capa}")[0]
                assert (float(central.get_xdata()[0]), float(central.get_ydata()[0])) == pytest.approx((0.0, c.central.fwhm_mm)) and c.central.k == 0
            zona = sorted(float(a.get_xdata()[0]) for a in por_gid(ax, "barrido:zona"))
            assert zona == pytest.approx(sorted(b.zona_mm))

    def test_el_barrido_no_tiene_selector_ni_ningun_control_que_cambie_un_parametro(self, solo_lectura):
        pestana = solo_lectura.v.pestanas.widget(3)
        controles = [w for w in recorrer(pestana) if isinstance(w, (QComboBox, QSpinBox, QDoubleSpinBox, QSlider, QCheckBox, QRadioButton, QPushButton, QLineEdit))]
        assert controles == [], "PD2: el barrido no tiene parametro que elegir"

    def test_la_tabla_de_los_barridos_dice_las_medidas_estadisticas_del_motor(self, solo_lectura, directo):
        filas = texto_de_la_tabla(solo_lectura.v.tabla_barridos)
        assert len(filas) == 8
        esperado = []
        for capa, nombre in (("R", "Capa roja"), ("G", "Capa verde"), ("B", "Capa azul"), ("gris", "Gris")):
            for eje in ("crossplane", "inplane"):
                c = directo.barrido.ejes[eje].capas[capa]
                e = c.estadistica
                esperado.append([nombre, eje, "ok", "79", "79", f"{e.media_mm:.3f}", f"{e.mediana_mm:.3f}", f"{e.desviacion_mm:.3f}", f"{c.central.fwhm_mm:.3f}", _con_signo(c.central.fwhm_mm - e.mediana_mm)])
        assert filas == esperado

    def test_la_tabla_de_los_barridos_mide_el_corte_central_contra_la_mediana_y_no_contra_la_media(self, directo):
        """En la sintetica la media y la mediana de las bandas coinciden y la tabla no distingue de cual se aleja el corte central: aqui se FABRICAN distintas (una mota desplaza la media y deja la mediana)."""
        barrido = directo.barrido
        eje = barrido.ejes["crossplane"]
        capa = eje.capas["gris"]
        e = capa.estadistica
        distinta = dataclasses.replace(e, media_mm=e.media_mm + 0.37, mediana_mm=e.mediana_mm - 0.21)
        otro = dataclasses.replace(barrido, ejes={**barrido.ejes, "crossplane": dataclasses.replace(eje, capas={**eje.capas, "gris": dataclasses.replace(capa, estadistica=distinta)})})
        fila = next(f for f in dibujo_mod().filas_de_los_barridos(otro) if f[0] == "Gris" and f[1] == "crossplane")
        assert fila[5] == f"{distinta.media_mm:.3f}" and fila[6] == f"{distinta.mediana_mm:.3f}" and fila[8] == f"{capa.central.fwhm_mm:.3f}"
        assert fila[9] == _con_signo(capa.central.fwhm_mm - distinta.mediana_mm) != _con_signo(capa.central.fwhm_mm - distinta.media_mm), "cuanto se aleja el corte central: de la MEDIANA"


class TestPestana5Cuadratura:
    def test_el_cuadrado_perfecto_es_el_del_lado_medio_sin_girar_y_con_el_mismo_centro(self, solo_lectura, directo):
        g = directo.resultado.geometria
        lado = float(np.mean(list(g.lados_mm.values())))
        perfecto = por_gid(solo_lectura.v.eje_cuadratura, "cuadratura:perfecto")[0]
        xy = list(zip(map(float, perfecto.get_xdata()), map(float, perfecto.get_ydata())))
        mitad = lado / 2
        assert xy == pytest.approx([(-mitad, -mitad), (mitad, -mitad), (mitad, mitad), (-mitad, mitad), (-mitad, -mitad)])
        centro = por_gid(solo_lectura.v.eje_cuadratura, "cuadratura:centro")[0]
        assert (float(centro.get_xdata()[0]), float(centro.get_ydata()[0])) == (0.0, 0.0)

    def test_el_recuadro_marcado_se_dibuja_a_escala_real_y_ampliado_veinte_veces(self, solo_lectura, directo):
        ax = solo_lectura.v.eje_cuadratura
        g = directo.resultado.geometria
        real = [(float((x - g.cruce[0]) * g.tam_mm), float((y - g.cruce[1]) * g.tam_mm)) for x, y in g.esquinas]
        lado = float(np.mean(list(g.lados_mm.values())))
        perfecto = [(-lado / 2, -lado / 2), (lado / 2, -lado / 2), (lado / 2, lado / 2), (-lado / 2, lado / 2)]
        linea = por_gid(ax, "cuadratura:real")[0]
        assert list(zip(map(float, linea.get_xdata()), map(float, linea.get_ydata())))[:4] == pytest.approx(real)
        ampliado = por_gid(ax, "cuadratura:ampliado")[0]
        esperado = [(px + 20 * (rx - px), py + 20 * (ry - py)) for (px, py), (rx, ry) in zip(perfecto, real)]
        assert list(zip(map(float, ampliado.get_xdata()), map(float, ampliado.get_ydata())))[:4] == pytest.approx(esperado), "las desviaciones se amplian un factor FIJO de 20"
        assert any("desviaciones × 20" in t for t in etiquetas(ax)) and "desviaciones × 20" in ax.get_title()

    def test_el_angulo_girado_va_en_el_titulo_con_signo_y_la_y_apunta_hacia_abajo_como_la_imagen(self, solo_lectura, directo):
        ax = solo_lectura.v.eje_cuadratura
        assert f"ángulo girado {_con_signo(directo.resultado.geometria.angulo_grados)}° frente a 0° del cuadrado perfecto" in ax.get_title()
        y0, y1 = ax.get_ylim()
        assert y0 > y1 and ax.get_aspect() == 1.0 and (ax.get_xlabel(), ax.get_ylabel()) == ("x desde el cruce de diagonales [mm]", "y desde el cruce de diagonales [mm]")

    def test_la_tabla_dice_lados_inclinaciones_angulos_interiores_diagonales_y_el_angulo_girado(self, solo_lectura, directo):
        g = directo.resultado.geometria
        filas = texto_de_la_tabla(solo_lectura.v.tabla_cuadratura)
        assert len(filas) == 15
        assert [f[0] for f in filas] == [f"Lado {n} [mm]" for n in ("superior", "derecho", "inferior", "izquierdo")] + [f"Inclinación del lado {n} [°]" for n in ("superior", "derecho", "inferior", "izquierdo")] \
            + [f"Ángulo interior {n} [°]" for n in ("superior izquierda", "superior derecha", "inferior derecha", "inferior izquierda")] + ["Diagonal principal [mm]", "Diagonal secundaria [mm]", "Ángulo girado [°]"]
        lado = float(np.mean(list(g.lados_mm.values())))
        for fila, nombre in zip(filas[:4], ("superior", "derecho", "inferior", "izquierdo")):
            assert fila[1] == f"{g.lados_mm[nombre]:.3f}" and fila[2] == f"{lado:.3f}" and fila[3] == _con_signo(g.lados_mm[nombre] - lado)
        assert [f[2] for f in filas[8:12]] == ["90.000"] * 4 and filas[12][2] == filas[13][2] == f"{lado * 2 ** 0.5:.3f}"
        assert filas[14] == ["Ángulo girado [°]", _con_signo(g.angulo_grados), "0.000", _con_signo(g.angulo_grados)]

    def test_cada_celda_de_la_tabla_es_el_numero_del_motor_con_su_referencia_y_su_diferencia(self, solo_lectura, directo):
        """E1-REV1-PRU-01 (ronda 1 de la revision). La prueba de arriba mira los rotulos, los lados y el angulo girado; de las inclinaciones, los angulos interiores y las diagonales no miraba ni el valor ni la
        diferencia (un signo cambiado en esas diez filas dejaba verdes las 153 pruebas). Aqui, las 15 filas y las 4 columnas, contra la geometria del motor con la aritmetica del plan escrita en la prueba."""
        assert texto_de_la_tabla(solo_lectura.v.tabla_cuadratura) == _filas_de_la_cuadratura_esperadas(directo.resultado.geometria)

    def test_con_un_campo_marcado_torcido_cada_celda_distingue_su_signo_y_su_columna(self, fabrica, dialogos, archivo_placa, clics, placa):
        """E1-REV1-PRU-01. En la sintetica sin girar casi todo vale 0.000 y un signo cambiado no se ve. Con dos esquinas marcadas lejos de donde estan (4 mm), el cuadrilatero deja de ser un cuadrado y las
        15 filas dan numeros lejos de cero y de signos distintos: inclinaciones de +3.3 a -2.9 grados, angulos interiores de 87.7 a 96.2, diagonales 2 mm por encima y por debajo de la perfecta."""
        cx, cy = placa.verdad.centro_campo_px
        esquinas = [i for i, c in enumerate(clics) if math.hypot(c[0] - cx, c[1] - cy) > 500]
        assert len(esquinas) == 4, "compuerta: cuatro de los cinco clics son esquinas y el quinto el reticulo"
        torcida = [tuple(map(float, c)) for c in clics]
        torcida[esquinas[0]] = (torcida[esquinas[0]][0] + 90.0, torcida[esquinas[0]][1] - 60.0)
        torcida[esquinas[1]] = (torcida[esquinas[1]][0] - 70.0, torcida[esquinas[1]][1] + 110.0)
        v = analizada(fabrica(), dialogos, archivo_placa, torcida)
        resultado, _barrido, _marcas = resultado_directo(placa.datos, torcida)
        g = resultado.geometria
        assert g.ok and max(abs(a) for a in g.inclinacion_de_los_lados_grados.values()) > 1.0 and max(abs(a - 90.0) for a in g.angulos_interiores_grados.values()) > 1.0, "premisa: no es un cuadrado"
        filas = texto_de_la_tabla(v.tabla_cuadratura)
        assert filas == _filas_de_la_cuadratura_esperadas(g)
        distintos = {f[3][0] for f in filas if f[3][0] in "+-"}
        assert distintos == {"+", "-"}, "compuerta: la tabla tiene diferencias de los dos signos"

    def test_con_la_pelicula_girada_el_angulo_girado_va_con_el_signo_del_giro_de_la_verdad(self, fabrica, dialogos, tmp_path):
        """El angulo girado de la tabla (y del titulo) tiene el signo del giro de la pelicula (positivo, en el sentido de las agujas del reloj, como lo fabrica el generador de PF.0): la verdad no sale del motor."""
        for theta in (0.8, -1.2):
            girada = gen.generar("png", variante="A", theta_deg=theta, seed=1)
            ruta = tmp_path / f"girada_{theta}.png"
            ruta.write_bytes(girada.datos)
            v = analizada(fabrica(), dialogos, str(ruta), [tuple(map(float, c)) for c in girada.verdad.clics_del_cuaderno()])
            fila = texto_de_la_tabla(v.tabla_cuadratura)[14]
            assert fila[0] == "Ángulo girado [°]" and float(fila[1]) == pytest.approx(theta, abs=0.02) and fila[3] == fila[1] and fila[2] == "0.000", (theta, fila)
            assert f"ángulo girado {fila[1]}° frente a 0° del cuadrado perfecto" in v.eje_cuadratura.get_title()

    def test_los_numeros_de_la_cuadratura_no_dependen_de_la_capa(self, solo_lectura):
        assert "capa" not in " ".join(c.lower() for c in texto_de_la_tabla(solo_lectura.v.tabla_cuadratura)[0])


# ================================================================================================= 5-bis. el estilo de cada linea (E1-REV1-PRU-02)

# El plan fija el estilo de varias lineas de las pestanas 3 y 4 («el nivel del piso, los limites de la meseta y de la exclusion central (punteadas), la media de la meseta (discontinua), la altura media
# (continua), los bordes de radiacion (verticales continuas)»; en los barridos «su media (discontinua), su mediana (punteada)») y la leyenda de los barridos lo escribe en palabras («media,
# discontinua», «mediana, punteada»): una linea con otro estilo hace que la leyenda MIENTA. Las pruebas de dibujo comparaban posiciones y `gid` con el motor, nunca el estilo (los mutantes m4 y m5
# del revisor, una mediana discontinua y una altura media discontinua, sobrevivian a las 153 pruebas). Matplotlib dice el estilo como '-' (continua), '--' (discontinua), ':' (punteada) y '-.'.
ESTILO_QUE_FIJA_EL_PLAN = {"perfil:zona": ":", "perfil:exclusion": ":", "perfil:meseta": "--", "perfil:altura_media": "-", "perfil:borde_rad": "-"}
ESTILO_DE_LA_PANTALLA = {"perfil:crudo": "-", "perfil:suavizado": "-", "perfil:piso": "-.", "perfil:penumbra_alta": ":", "perfil:penumbra_baja": ":", "perfil:borde_luz": "-.", "perfil:cruce": "-"}
VERTICALES_DE_UN_PERFIL = ("perfil:zona", "perfil:exclusion", "perfil:borde_luz", "perfil:borde_rad", "perfil:cruce")
HORIZONTALES_DE_UN_PERFIL = ("perfil:piso", "perfil:meseta", "perfil:altura_media", "perfil:penumbra_alta", "perfil:penumbra_baja")
PALABRA_DEL_ESTILO = {"discontinua": "--", "punteada": ":"}                  # lo que una leyenda dice con palabras


class TestElEstiloDeCadaLinea:
    def test_cada_linea_de_un_perfil_tiene_el_estilo_que_fija_el_plan_o_el_de_la_pantalla(self, solo_lectura):
        for (capa, eje), ax in _grupo(solo_lectura.v).items():
            for gid, estilo in {**ESTILO_QUE_FIJA_EL_PLAN, **ESTILO_DE_LA_PANTALLA}.items():
                lineas = por_gid(ax, gid)
                assert lineas, (capa, eje, gid, "el perfil dibuja esa linea")
                assert [l.get_linestyle() for l in lineas] == [estilo] * len(lineas), (capa, eje, gid, [l.get_linestyle() for l in lineas])

    def test_los_bordes_los_limites_y_el_cruce_son_lineas_verticales_y_los_niveles_horizontales(self, solo_lectura):
        for (capa, eje), ax in _grupo(solo_lectura.v).items():
            for gid in VERTICALES_DE_UN_PERFIL:
                assert all(l.get_xdata()[0] == l.get_xdata()[1] and l.get_ydata()[0] != l.get_ydata()[1] for l in por_gid(ax, gid)), (capa, eje, gid, "vertical: la misma x, otra y")
            for gid in HORIZONTALES_DE_UN_PERFIL:
                assert all(l.get_ydata()[0] == l.get_ydata()[1] and l.get_xdata()[0] != l.get_xdata()[1] for l in por_gid(ax, gid)), (capa, eje, gid, "horizontal: la misma y, otra x")

    def test_en_los_barridos_la_media_es_discontinua_la_mediana_punteada_y_la_leyenda_lo_dice_con_el_estilo_que_dibuja(self, solo_lectura):
        for ax in solo_lectura.v._fig_barridos.axes:
            for capa in (*CAPAS, "gris"):
                assert [l.get_linestyle() for l in por_gid(ax, f"barrido:media:{capa}")] == ["--"], (capa, "la media, discontinua")
                assert [l.get_linestyle() for l in por_gid(ax, f"barrido:mediana:{capa}")] == [":"], (capa, "la mediana, punteada")
                assert [l.get_linestyle() for l in por_gid(ax, f"barrido:bandas:{capa}")] == ["-"], (capa, "el FWHM de las bandas, una linea continua con sus puntos")
                central = por_gid(ax, f"barrido:central:{capa}")
                assert [(l.get_linestyle(), l.get_marker()) for l in central] == [("None", "D")], (capa, "el corte central es un rombo suelto, sin linea")
            assert [l.get_linestyle() for l in por_gid(ax, "barrido:zona")] == ["-."] * 2, "los limites de la zona central"
            estilo_de = {etiqueta: h.get_linestyle() for h, etiqueta in zip(*ax.get_legend_handles_labels())}
            assert estilo_de["media, discontinua"] == "--" and estilo_de["mediana, punteada"] == ":"
            for etiqueta, estilo in estilo_de.items():
                for palabra, esperado in PALABRA_DEL_ESTILO.items():
                    assert palabra not in etiqueta or estilo == esperado, f"la leyenda dice «{etiqueta}» y la linea es {estilo!r}: la leyenda miente"

    def test_ninguna_leyenda_de_ninguna_figura_dice_un_estilo_que_su_linea_no_tiene(self, solo_lectura):
        """La misma regla para TODA leyenda de las seis figuras (la de los ejes y la de la figura entera): si una etiqueta nombra un estilo con palabras, el trazo de ese renglon lo tiene."""
        v = solo_lectura.v
        vistas = 0
        for lienzo in (v.lienzo_imagen, v.lienzo_gris, v.lienzo_capas, v.lienzo_perfiles, v.lienzo_barridos, v.lienzo_cuadratura):
            figura = lienzo.figure
            for leyenda in [*figura.legends, *[ax.get_legend() for ax in figura.axes if ax.get_legend() is not None]]:
                for texto, manejador in zip(leyenda.get_texts(), getattr(leyenda, "legend_handles", None) or leyenda.legendHandles):
                    vistas += 1
                    for palabra, estilo in PALABRA_DEL_ESTILO.items():
                        assert palabra not in texto.get_text() or manejador.get_linestyle() == estilo, (texto.get_text(), manejador.get_linestyle())
        assert vistas > 20, "compuerta: el censo recorre las leyendas de verdad"


# ================================================================================================= 6-bis. las funciones puras de dibujo y de texto

class TestLasFuncionesPuras:
    """Los dibujos y los textos viven en un modulo sin Qt (`analisisImagenes/dibujo_placa_mensual.py`): se prueban sin ventana, con los casos que una pelicula real no siempre produce."""

    def test_numero_nunca_escribe_un_cero_con_signo(self):
        d = dibujo_mod()
        # B.8 (DA-88, clase b): lo que no se midio se dice «no medible»; esta asercion decia «sin dato» (el fisico decidio la palabra el 22-10). Lo demas de la prueba no cambia.
        assert d.numero(None) == "no medible" and d.numero(0.0004, 3, True) == "0.000" and d.numero(-0.0004, 3, True) == "0.000" and d.numero(-0.0006, 3, True) == "-0.001"
        assert d.numero(1.23456, 2) == "1.23" and d.numero(5, 3, True) == "+5.000" and d.numero(-5, 3, True) == "-5.000" and d.numero(-0.0004, 3) == "0.000"

    def test_colorear_es_el_mapa_jet_en_rgba_uint8_y_un_nan_queda_transparente(self):
        c = dibujo_mod().colorear(np.array([0.0, 0.5, 1.0, np.nan, -3.0, 7.0]))
        assert c.dtype == np.uint8 and c.shape == (6, 4)
        assert c[0].tolist() == [0, 0, 127, 255] and c[2].tolist() == [127, 0, 0, 255], "jet: del azul oscuro (el piso) al rojo oscuro (la meseta)"
        assert c[1][1] == 255 and abs(int(c[1][0]) - int(c[1][2])) < 10 and 100 < c[1][0] < 140, "en el medio, verde"
        assert c[3][3] == 0, "un NaN (lo que no tiene dato) queda transparente"
        assert c[4].tolist() == c[0].tolist() and c[5].tolist() == c[2].tolist(), "lo que se sale de 0 a 1 se recorta"

    def test_a_imagen_es_la_inversa_del_giro_del_motor(self):
        M = pm().matriz_giro((1350.0, 1300.0), 3.0)
        puntos = [(10.0, 20.0), (300.5, 40.25), (150.0, 2500.0), (2700.0, 2700.0)]
        girados = pm().transformar_puntos(M, puntos)
        assert np.allclose(np.array(dibujo_mod().a_imagen(M, [tuple(p) for p in girados])), np.array(puntos), atol=1e-9)
        assert not np.allclose(np.array(girados), np.array(puntos), atol=1.0), "compuerta: el giro de 3 grados si mueve los puntos"

    def test_zona_central_es_none_sin_barrido_o_sin_la_region_de_un_eje(self, directo):
        d, b = dibujo_mod(), directo.barrido
        assert d.zona_central(directo.resultado, None) is None
        for eje in ("crossplane", "inplane"):
            sin_region = dataclasses.replace(b, ejes={**b.ejes, eje: dataclasses.replace(b.ejes[eje], zona_px=None)})
            assert d.zona_central(directo.resultado, sin_region) is None, eje
        assert d.zona_central(directo.resultado, b) == (tuple(b.ejes["inplane"].zona_px), tuple(b.ejes["crossplane"].zona_px)), "compuerta: con el barrido entero la zona esta"

    def test_en_valor_de_pixel_una_capa_sin_piso_o_sin_meseta_se_pinta_en_niveles_y_dice_por_que(self, directo):
        # CD.1 (23-10, clase b): ya no hay una capa que se deje tal cual dividida entre 255: en valor de pixel (la base de E.1) toda capa se pinta en niveles de 0 a 255 y su texto dice el piso y la meseta
        # o por que faltan (`CapaEnUnidades`: el arreglo en niveles, el tope 255, la unidad, el texto).
        d, r = dibujo_mod(), directo.resultado
        capa = r.capas["R"]

        def con(**cambios):
            return dataclasses.replace(r, capas={**r.capas, "R": dataclasses.replace(capa, **cambios)})

        c = d.capa_acondicionada(con(piso=None, estado="no medible: no hay piso"), "R")
        assert c.texto == "valor de píxel de 0 a 255 [nivel]; no medible: no hay piso" and c.tope == 255.0 and c.unidad == "valor de píxel [nivel]"
        assert c.valores.dtype == np.float32 and 0.0 <= np.nanmin(c.valores) and np.nanmax(c.valores) <= 255.0 and np.nanmax(c.valores) > 1.0
        sin_mesetas = con(crossplane=dataclasses.replace(capa.crossplane, meseta=None), inplane=dataclasses.replace(capa.inplane, meseta=None))
        c = d.capa_acondicionada(sin_mesetas, "R")
        assert c.meseta is None and c.texto == "valor de píxel de 0 a 255 [nivel]; la capa no tiene meseta medida" and c.tope == 255.0 and c.unidad == "valor de píxel [nivel]"
        normal = d.capa_acondicionada(r, "R")
        assert normal.meseta is not None and normal.texto.startswith("valor de píxel de 0 a 255 [nivel]; piso "), "compuerta: la capa entera dice su piso y su meseta"

    def test_el_barrido_de_una_capa_sin_bandas_no_dibuja_esa_capa_y_sigue_con_las_otras(self, directo):
        b = directo.barrido
        ejes = {e: dataclasses.replace(x, capas={**x.capas, "R": dataclasses.replace(x.capas["R"], bandas=())}) for e, x in b.ejes.items()}
        figura = Figure()
        dibujo_mod().dibujar_barridos(figura, dataclasses.replace(b, ejes=ejes))
        assert len(figura.axes) == 2
        for ax in figura.axes:
            gids = {l.get_gid() for l in ax.get_lines()}
            assert "barrido:bandas:R" not in gids and {"barrido:bandas:G", "barrido:bandas:B", "barrido:bandas:gris"} <= gids

    def test_el_barrido_con_la_roja_sin_medir_rotula_igual_el_corte_central_la_media_y_la_mediana(self, directo):
        """E1-R2-PROD-01 con la figura sola: la roja dibuja sus bandas (como huecos) pero no tiene corte central, media ni mediana; las otras capas SI los tienen y la leyenda los nombra UNA vez por eje."""
        b = directo.barrido

        def sin_medir(eje):
            capa = eje.capas["R"]
            bandas = tuple(dataclasses.replace(banda, medida=dataclasses.replace(banda.medida, estado="no medible: de prueba", fwhm_mm=None)) for banda in capa.bandas)
            estadistica = dataclasses.replace(capa.estadistica, n_medibles=0, media_mm=None, mediana_mm=None, desviacion_mm=None)
            return dataclasses.replace(eje, capas={**eje.capas, "R": dataclasses.replace(capa, estado="no medible: de prueba", bandas=bandas, estadistica=estadistica)})
        figura = Figure()
        dibujo_mod().dibujar_barridos(figura, dataclasses.replace(b, ejes={e: sin_medir(x) for e, x in b.ejes.items()}))
        assert len(figura.axes) == 2
        for ax in figura.axes:
            assert not (por_gid(ax, "barrido:central:R") or por_gid(ax, "barrido:media:R") or por_gid(ax, "barrido:mediana:R")), "premisa: la roja no dibuja nada de eso"
            assert por_gid(ax, "barrido:central:G") and por_gid(ax, "barrido:media:G") and por_gid(ax, "barrido:mediana:G"), "premisa: las otras capas si"
            textos = etiquetas(ax)
            assert [textos.count(r) for r in ("corte central, banda 0", "media, discontinua", "mediana, punteada")] == [1, 1, 1], textos

    @pytest.mark.parametrize("dpi,clase,resto", [
        (600.0, "coincide", "resolución declarada 600 dpi, igual que la del procedimiento"),
        (None, "sin_dato", "el archivo no declara su resolución: se usa la del procedimiento, 600 dpi"),
        (96.012, "editor", "el archivo declara 96.01 dpi, lo que escribe un editor al guardar un recorte: se usa la del procedimiento, 600 dpi"),
        (300.0, "otra", "el archivo declara 300 dpi y el procedimiento es de 600 dpi: sin esa escala no hay milímetros ni medidas")])
    def test_texto_de_la_imagen_dice_cada_clase_de_resolucion(self, dpi, clase, resto):
        assert dibujo_mod().texto_de_la_imagen("PNG", 8, (2734, 2710), dpi, clase, None, 0, 600.0) == f"PNG, 8 bits por canal, 2710 × 2734 px. {resto}."

    def test_texto_de_la_imagen_dice_la_fecha_los_transparentes_y_un_formato_desconocido(self):
        from datetime import date
        texto = dibujo_mod().texto_de_la_imagen(None, 16, (10, 20), 600.0, "coincide", date(2026, 10, 5), 7, 600.0)
        assert texto == "formato desconocido, 16 bits por canal, 20 × 10 px. resolución declarada 600 dpi, igual que la del procedimiento. escaneada el 2026-10-05. 7 píxeles transparentes, que son sin dato."

    def test_texto_de_las_marcas_cuenta_las_refinadas_y_dice_el_motivo_de_cada_una_sin_refinar(self):
        d = dibujo_mod()
        refinada = lambda i, mm: {"estado": pm().ESTADO_REFINADA, "clic": [i, i], "punto": [i + 0.5, i], "radio_px": 35.4, "desplazamiento_mm": mm, "motivo": None}
        assert d.texto_de_las_marcas([]) == ""
        assert d.texto_de_las_marcas([(1, 2), (3, 4)]) == "Marcas 2 de 5. Ninguna refinada.\nMarca 1: sin refinar\nMarca 2: sin refinar"
        assert d.texto_de_las_marcas([refinada(1, 0.25), (3, 4), refinada(5, 0.0625)]) == "Marcas 3 de 5. Refinadas: 1, 3; el punto se movió de 0.062 a 0.250 mm del clic.\nMarca 2: sin refinar"
        con_motivo = {"estado": "sin refinar", "clic": [1, 1], "punto": [1, 1], "radio_px": None, "motivo": "sin refinar: no hay tinta"}
        assert d.texto_de_las_marcas([con_motivo]).endswith("Marca 1: sin refinar: no hay tinta")

    def test_texto_de_las_marcas_sin_escala_dice_lo_que_se_movio_el_punto_en_pixeles_y_nunca_en_milimetros(self):
        """E1-PROD-02: `con_milimetros=False` (el archivo declara otra resolucion: no hay escala) cambia la unidad del rango por los pixeles, que el motor ya trae; el resto del texto, incluidas las marcas
        sin refinar y su motivo, es el de siempre. Por omision (`con_milimetros=True`) el texto es el de hoy."""
        d = dibujo_mod()
        refinada = lambda i, px, mm: {"estado": pm().ESTADO_REFINADA, "clic": [i, i], "punto": [i + 0.5, i], "radio_px": 35.4, "desplazamiento_px": px, "desplazamiento_mm": mm, "motivo": None}
        marcas = [refinada(1, 0.5, 0.0212), (3, 4), refinada(5, 0.0625, 0.0026)]
        assert d.texto_de_las_marcas(marcas) == "Marcas 3 de 5. Refinadas: 1, 3; el punto se movió de 0.003 a 0.021 mm del clic.\nMarca 2: sin refinar"
        assert d.texto_de_las_marcas(marcas, con_milimetros=True) == d.texto_de_las_marcas(marcas)
        sin_escala = d.texto_de_las_marcas(marcas, con_milimetros=False)
        assert sin_escala == "Marcas 3 de 5. Refinadas: 1, 3; el punto se movió de 0.06 a 0.50 px del clic.\nMarca 2: sin refinar" and "mm" not in sin_escala
        assert d.texto_de_las_marcas([(1, 2), (3, 4)], con_milimetros=False) == "Marcas 2 de 5. Ninguna refinada.\nMarca 1: sin refinar\nMarca 2: sin refinar"
        sin_pixeles = {"estado": pm().ESTADO_REFINADA, "clic": [1, 1], "punto": [1, 1], "radio_px": 35.4, "desplazamiento_mm": 0.02, "motivo": None}
        assert d.texto_de_las_marcas([sin_pixeles], con_milimetros=False) == "Marcas 1 de 5. Refinadas: 1.", "una marca guardada sin sus pixeles no inventa un rango, ni lo dice en milimetros"

    def test_filas_de_la_cuadratura_con_numeros_hechos_a_mano_dicen_cada_columna_y_cada_signo(self):
        """E1-REV1-PRU-01. Una geometria FABRICADA con numeros distintos y lejos de cero (el lado medio es 100.000, la diagonal perfecta 141.421) y las 15 filas escritas aqui a mano, a ojo y sin formulas:
        cada diferencia es «medido menos perfecto» y lleva su signo (la inclinacion y el angulo girado se comparan con 0, los angulos interiores con 90, las diagonales con la perfecta)."""
        g = pm().GeometriaLuz("ok", lados_mm={"superior": 99.0, "derecho": 100.0, "inferior": 101.0, "izquierdo": 100.0},
                              inclinacion_de_los_lados_grados={"superior": 0.25, "derecho": -0.5, "inferior": 0.75, "izquierdo": -1.0},
                              angulos_interiores_grados={"UL": 89.5, "UR": 90.25, "DR": 90.5, "DL": 89.75}, diagonales_mm=(141.0, 142.0), angulo_grados=-0.375)
        assert dibujo_mod().filas_de_la_cuadratura(g) == [
            ("Lado superior [mm]", "99.000", "100.000", "-1.000"), ("Lado derecho [mm]", "100.000", "100.000", "0.000"),
            ("Lado inferior [mm]", "101.000", "100.000", "+1.000"), ("Lado izquierdo [mm]", "100.000", "100.000", "0.000"),
            ("Inclinación del lado superior [°]", "+0.250", "0.000", "+0.250"), ("Inclinación del lado derecho [°]", "-0.500", "0.000", "-0.500"),
            ("Inclinación del lado inferior [°]", "+0.750", "0.000", "+0.750"), ("Inclinación del lado izquierdo [°]", "-1.000", "0.000", "-1.000"),
            ("Ángulo interior superior izquierda [°]", "89.500", "90.000", "-0.500"), ("Ángulo interior superior derecha [°]", "90.250", "90.000", "+0.250"),
            ("Ángulo interior inferior derecha [°]", "90.500", "90.000", "+0.500"), ("Ángulo interior inferior izquierda [°]", "89.750", "90.000", "-0.250"),
            ("Diagonal principal [mm]", "141.000", "141.421", "-0.421"), ("Diagonal secundaria [mm]", "142.000", "141.421", "+0.579"),
            ("Ángulo girado [°]", "-0.375", "0.000", "-0.375")]
        assert _filas_de_la_cuadratura_esperadas(g) == [list(f) for f in dibujo_mod().filas_de_la_cuadratura(g)], "el oraculo de las pruebas de la ventana dice lo mismo que los numeros escritos a mano"

    def test_texto_de_la_regla_nombra_las_capas_medibles_en_el_orden_de_las_capas_y_dice_ninguna_una_vez(self):
        regla = dibujo_mod().texto_de_la_regla
        assert regla("M", ()) == "No se puede guardar: M." + " Ninguna de las tres capas es medible en esta película: de este análisis no se guarda nada, ni la imagen."
        assert regla("M", ("B",)) == "No se puede guardar: M. En esta película sí se puede guardar la capa azul; elíjala en el menú «Capa reportada»."
        assert regla("M", ("B", "R")) == "No se puede guardar: M. En esta película sí se pueden guardar: rojo y azul; elija una en el menú «Capa reportada»."
        assert regla("M", ("G", "R", "B")) == "No se puede guardar: M. En esta película sí se pueden guardar: rojo, verde y azul; elija una en el menú «Capa reportada»."

    def test_texto_de_la_regla_cierra_con_un_solo_punto_el_texto_del_servicio_lo_traiga_o_no(self):
        """E1-R2-PROD-03: el texto del servicio va TAL CUAL con el prefijo de la ventana; si ya termina en un signo final no se le agrega un punto mas."""
        regla = dibujo_mod().texto_de_la_regla
        assert regla("M.", ("B",)) == "No se puede guardar: M. En esta película sí se puede guardar la capa azul; elíjala en el menú «Capa reportada»."
        assert regla("¿M?", ()) == "No se puede guardar: ¿M? Ninguna de las tres capas es medible en esta película: de este análisis no se guarda nada, ni la imagen."

    @pytest.mark.parametrize("texto,esperado", [("", ""), ("   ", "   "), ("algo", "algo."), ("algo.", "algo."), ("algo?", "algo?"), ("algo!", "algo!"), ("algo...", "algo..."),
                                               ("algo (con paréntesis)", "algo (con paréntesis)."), ("algo «entre comillas»", "algo «entre comillas»."), ("algo.\n", "algo.\n"), ("algo \n", "algo."),
                                               ("dos. frases", "dos. frases.")])
    def test_con_punto_final_agrega_el_punto_solo_si_falta(self, texto, esperado):
        """E1-R2-PROD-02 y -03: la ÚNICA definición de «cerrar una frase»: junta una frase ajena con la que sigue (la linea del piso) y cierra un mensaje ajeno (el aviso de un guardado rechazado) sin duplicar su punto."""
        assert dibujo_mod().con_punto_final(texto) == esperado

    def test_detalle_de_la_referencia_virgen_dice_la_fecha_del_escaneo_o_que_el_archivo_no_la_trae(self):
        """E1-R2-PROD-04: la fila de auditoría de «Guardar como referencia» dice «escaneada el <fecha>» o «sin fecha de escaneo», nunca «escaneada el sin fecha»."""
        detalle = dibujo_mod().detalle_de_la_referencia_virgen
        base = {"archivo": "v.tif", "formato": "TIFF", "bits": 8, "orientacion_declarada": "girada"}
        assert detalle({**base, "fecha_escaneo": "2026-10-13"}) == "referencia de la película virgen «v.tif»; TIFF; 8 bits; escaneada el 2026-10-13; orientación girada"
        for sin_fecha in ({**base, "fecha_escaneo": None}, {**base, "fecha_escaneo": ""}, base):
            assert detalle(sin_fecha) == "referencia de la película virgen «v.tif»; TIFF; 8 bits; sin fecha de escaneo; orientación girada"

    @pytest.mark.parametrize("capa,reportada,motivo,registro,esperado", [
        ("G", "G", None, False, "se guarda"), ("G", "G", "M", False, "no se guarda: no es medible"), ("R", "G", None, False, ""), ("R", "G", "M", False, ""),
        ("G", "G", None, True, "guardada"), ("G", "G", "M", True, "guardada; en lo recalculado no es medible"), ("B", "G", "M", True, ""), ("gris", "G", None, False, "")])
    def test_texto_se_guarda_solo_lo_dice_la_fila_de_la_capa_reportada(self, capa, reportada, motivo, registro, esperado):
        assert dibujo_mod().texto_se_guarda(capa, reportada, motivo, registro) == esperado

    @pytest.mark.parametrize("motivo,reportada,registro,esperado", [
        (None, "G", False, "Estos son los desfases del perfil de grises. Lo que se guarda y se imprime es lo de la capa verde, que se ve en la pestaña 3."),
        ("MOTIVO", "G", False, "MOTIVO"),
        (None, "B", True, "Estos son los desfases del perfil de grises. Lo guardado y lo que imprime el PDF es la capa azul, que se ve en la pestaña 3."),
        ("MOTIVO", "R", True, "Estos son los desfases del perfil de grises. Lo guardado y lo que imprime el PDF es la capa roja, que se ve en la pestaña 3."),
        (None, None, True, "Estos son los desfases del perfil de grises. Este registro no guardó ninguna capa reportada."),
        (None, None, False, "Estos son los desfases del perfil de grises. Lo que se guarda y se imprime es lo de ninguna capa, que se ve en la pestaña 3.")])
    def test_nota_de_la_pestana_1_dice_lo_que_se_guarda_o_el_texto_del_servicio_tal_cual(self, motivo, reportada, registro, esperado):
        assert dibujo_mod().nota_de_la_pestana_1(motivo, reportada, registro) == esperado

    def test_titulo_del_perfil_dice_la_capa_el_eje_el_fwhm_y_si_es_la_reportada(self):
        d = dibujo_mod()
        medida = lambda ok: SimpleNamespace(ok=ok, eje="crossplane", fwhm_mm=100.1234)
        assert d.titulo_del_perfil(medida(True), "R") == "Capa roja, crossplane: FWHM 100.123 mm" and d.titulo_del_perfil(medida(True), "gris") == "Gris, crossplane: FWHM 100.123 mm"
        assert d.titulo_del_perfil(medida(True), "G", reportada=True) == "Capa verde (reportada), crossplane: FWHM 100.123 mm"
        assert d.titulo_del_perfil(medida(False), "B") == "Capa azul, crossplane: no medible" and d.titulo_del_perfil(medida(False), "B", True) == "Capa azul (reportada), crossplane: no medible"

    def test_el_pie_de_parametros_acepta_listas_diccionarios_y_booleanos(self):
        pie = dibujo_mod().texto_de_parametros()
        assert "dpi de editor (72, 96)" in pie and "rango esperado del piso: R 60 a 140, G 145 a 200, B 65 a 100, gris 110 a 170" in pie and "se aparta del piso el borde de la imagen: sí" in pie


# ================================================================================================= 7. PD1 por censo, DA-18 y PD3

def _funciones_alcanzables(fuentes, raices):
    """{nombre: nodo} de las funciones que se alcanzan por llamadas por nombre (`f(...)` o `modulo.f(...)`) desde las raices, en los modulos dados (texto de cada uno)."""
    definidas = {}
    for texto in fuentes:
        for nodo in ast.walk(ast.parse(texto)):
            if isinstance(nodo, ast.FunctionDef):
                definidas.setdefault(nodo.name, nodo)
    vistas, cola = {}, list(raices)
    while cola:
        nombre = cola.pop()
        if nombre in vistas or nombre not in definidas:
            continue
        vistas[nombre] = definidas[nombre]
        for c in ast.walk(definidas[nombre]):
            if isinstance(c, ast.Call):
                destino = c.func.id if isinstance(c.func, ast.Name) else c.func.attr if isinstance(c.func, ast.Attribute) else None
                if destino in definidas:
                    cola.append(destino)
    return vistas


def parametros_que_entran_en_la_medida(fuentes, claves):
    """Las claves de `claves` (todos los parametros) que aparecen como constante de texto en las funciones alcanzables desde `analizar`, `barrido`, `refinar_marca` y el piso: `P["x"]`, `P.get("x")`, `_pedir(P, ("x",))` y
    el `P['x']` dentro de un mensaje (f-string) son todas constantes de texto."""
    funciones = _funciones_alcanzables(fuentes, ("analizar", "barrido", "refinar_marca", "piso_de_pelicula", "perfil_central", "girar"))
    encontradas = set()
    for nodo in funciones.values():
        for c in ast.walk(nodo):
            if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value in claves:
                encontradas.add(c.value)
    return encontradas, set(funciones)


class TestCadaParametroTieneSuTrazo:
    def test_el_censo_encuentra_los_parametros_de_verdad(self):
        claves, funciones = parametros_que_entran_en_la_medida([MOTOR_PY.read_text(encoding="utf-8"), PELICULA_PY.read_text(encoding="utf-8")], set(_P()))
        assert {"analizar", "medir_perfil", "refinar_marca", "piso_de_pelicula", "perfil_central", "girar", "barrido"} <= funciones, sorted(funciones)
        assert len(claves) >= 25 and claves <= set(_P()), "el censo no pasa en vacio"

    def test_cada_parametro_que_entra_en_la_medida_tiene_su_entrada_en_trazo_de_parametro(self):
        trazo = dibujo_mod().TRAZO_DE_PARAMETRO
        claves, _ = parametros_que_entran_en_la_medida([MOTOR_PY.read_text(encoding="utf-8"), PELICULA_PY.read_text(encoding="utf-8")], set(_P()))
        claves = claves - {"diferencia_virgen_maxima_pct"}      # CD.6 (31-10): el 42 es `diferencia_virgen_maxima_pct` (`PARAMETROS_DE_LA_DOSIS`): dice cuando se avisa y no entra en ninguna medida; su entrada la pone CD.7 (H-CD6-6), que quita esta resta
        assert not sorted(claves - set(trazo)), f"parametros que entran en una medida y no dicen donde se ven: {sorted(claves - set(trazo))}"

    def test_las_entradas_son_exactamente_los_40_parametros_y_declaran_un_tipo_conocido(self):
        trazo = dibujo_mod().TRAZO_DE_PARAMETRO
        assert set(trazo) == set(_P()) - {"diferencia_virgen_maxima_pct"} and len(trazo) == 41      # OD.1: eran 40; la base de la medida es el 41. CD.6 (31-10): el 42 es `diferencia_virgen_maxima_pct` (`PARAMETROS_DE_LA_DOSIS`): lo dibuja CD.7 (H-CD6-6)
        tipos = {"marca", "sexto", "banda", "zona", "perfil", "exclusion", "pagina", "pie"}
        assert all(isinstance(v, tuple) and len(v) == 2 and v[0] in tipos and isinstance(v[1], str) and v[1] for v in trazo.values())

    def test_el_censo_nombra_un_parametro_nuevo_que_nadie_dibuja(self):
        fuente = MOTOR_PY.read_text(encoding="utf-8")
        ancla = "    radio_px = P[\"radio_marca_mm\"] / tam_mm\n"
        assert fuente.count(ancla) == 1, "compuerta: el ancla de la fuente sintetica existe una sola vez"
        claves = set(_P()) | {"parametro_nuevo"}
        con, _ = parametros_que_entran_en_la_medida([fuente.replace(ancla, ancla + "    _ = P[\"parametro_nuevo\"]\n"), PELICULA_PY.read_text(encoding="utf-8")], claves)
        sin, _ = parametros_que_entran_en_la_medida([fuente, PELICULA_PY.read_text(encoding="utf-8")], claves)
        assert "parametro_nuevo" in con and "parametro_nuevo" not in sin

    def test_cada_entrada_esta_de_verdad_en_la_ventana(self, solo_lectura):
        v, d = solo_lectura.v, dibujo_mod()
        P = v._resultado.parametros
        etiquetas_imagen = [_normalizar_texto(e) for e in etiquetas(v.eje_imagen)]
        perfiles = list(_grupo(v).values())
        pie = v.pie_de_parametros.text()
        faltan = []
        for clave, (donde, texto) in sorted(d.TRAZO_DE_PARAMETRO.items()):
            if donde in ("marca", "banda", "zona"):
                ok = any(e.startswith(texto) for e in etiquetas_imagen)
            elif donde == "sexto":
                ok = True                                                    # se prueba con el sexto clic: `test_el_sexto_clic_tiene_su_trazo`
            elif donde in ("perfil", "exclusion"):
                ok = all(any(e.startswith(texto) for e in etiquetas_del_perfil(ax)) for ax in perfiles)
            elif donde == "pagina":
                valor = P[clave]
                ok = all(f"{x:g}" in getattr(v, texto).text() for x in (valor if isinstance(valor, (list, tuple)) else [valor]))
            else:
                ok = _frase_del_pie(texto, P[clave]) in pie
            if not ok:
                faltan.append((clave, donde, texto))
        assert not faltan, f"parametros cuyo trazo o rotulo declarado no esta en la ventana: {faltan}"

    def test_el_sexto_clic_tiene_su_trazo(self, fabrica, dialogos, archivo_placa):
        v = fabrica()
        cargar(v, dialogos, archivo_placa)
        v.boton_sexto.click()
        clic(v, 87, 87)
        texto = dibujo_mod().TRAZO_DE_PARAMETRO["lado_punto_manual_mm"][1]
        assert texto == "cuadrado del punto marcado" and texto in [_normalizar_texto(e) for e in etiquetas(v.eje_imagen)]

    def test_el_pie_dice_los_valores_con_que_se_midio_y_no_los_de_fabrica(self, solo_lectura):
        pie = dibujo_mod().texto_de_parametros({**_P(), "iqr_maximo": 7.0, "esquinas_minimas": 2, "apartar_borde_de_la_imagen": False})
        assert "dispersión de una esquina hasta 7 niveles" in pie and "al menos 2 esquinas con piso válido" in pie and "se aparta del piso el borde de la imagen: no" in pie
        assert "hasta 15 niveles" not in pie

    def test_el_pie_no_pasa_de_su_largo_y_ninguna_frase_queda_partida(self):
        d = dibujo_mod()
        lineas = d.texto_de_parametros().splitlines()
        assert len(lineas) >= 3 and all(len(l) <= d.LARGO_DEL_PIE for l in lineas)
        for clave, (donde, plantilla) in d.TRAZO_DE_PARAMETRO.items():
            if donde == "pie":
                assert sum(_frase_del_pie(plantilla, _P()[clave]) in l for l in lineas) == 1, (clave, lineas)


def etiquetas_del_perfil(ax):
    """Las etiquetas de los trazos de un perfil (la leyenda es de la figura, asi que se piden a los artistas)."""
    return [_normalizar_texto(h.get_label()) for h in ax.get_lines() + ax.patches if not h.get_label().startswith("_")]


def _frase_del_pie(plantilla, valor):
    """La frase del pie con el valor con que se midio (el ORACULO de la prueba: no llama a la produccion). Una lista se dice con comas, un diccionario por capa y un booleano con si o no."""
    if isinstance(valor, bool):
        valor = "sí" if valor else "no"
    elif isinstance(valor, dict):
        valor = ", ".join(f"{k} {v[0]:g} a {v[1]:g}" for k, v in valor.items())
    elif isinstance(valor, (list, tuple)):
        valor = ", ".join(f"{x:g}" for x in valor)
    return plantilla.format(valor)


class TestNingunControlCambiaUnNumero:
    def test_los_unicos_controles_editables_son_los_declarados(self, solo_lectura):
        v = solo_lectura.v
        todos = list(recorrer(v))
        botones = [w.text() for w in todos if isinstance(w, QPushButton)]
        assert sorted(botones) == sorted(["Seleccionar imagen", "Marcar película sin irradiar", "Película virgen...", "Recalcular", "Limpiar", "Guardar"])
        assert sorted(type(w).__name__ for w in todos if isinstance(w, QComboBox)) == ["_SelectorSinRueda", "_SelectorSinRueda"]
        prohibidos = (QSpinBox, QDoubleSpinBox, QSlider, QCheckBox, QRadioButton)
        assert not [w for w in todos if isinstance(w, prohibidos)], "ningun deslizador, caja de numero ni casilla: nada que mueva un parametro"
        lineas = [w for w in todos if isinstance(w, QLineEdit)]
        assert lineas == [v.nombre_archivo] and v.nombre_archivo.isReadOnly(), "el unico campo de texto es el nombre del archivo y no se puede escribir"
        assert all(t.editTriggers() == t.NoEditTriggers for t in todos if isinstance(t, QTableWidget)), "las tablas son de solo lectura"

    def test_los_dos_menus_son_los_declarados_y_ninguno_pone_un_numero(self, solo_lectura):
        v = solo_lectura.v
        assert [v.selector_capa.itemData(i) for i in range(3)] == ["R", "G", "B"] and [v.selector_piso.itemData(i) for i in range(3)] == list(pel().MODOS_DEL_PISO)
        assert not v.selector_capa.isEditable() and not v.selector_piso.isEditable(), "los dos menus se eligen, no se escriben: un menu editable aceptaria un texto (el campo interno lo crea Qt y el censo de widgets no lo ve)"


class TestLoQueLaVentanaDice:
    def test_ningun_texto_lleva_simbolos_de_correcto_o_incorrecto(self, solo_lectura):
        textos = todos_los_textos(solo_lectura.v)
        assert len(textos) > 100, "compuerta: el censo de textos no pasa en vacio"
        assert not [t for t in textos if not sin_simbolos(t)]

    def test_las_unidades_van_entre_corchetes_y_no_entre_parentesis(self, solo_lectura):
        parentesis = re.compile(r"\((?:mm|px|°|nivel|niveles|%|dpi|MeV|MV)\)")
        assert not [t for t in todos_los_textos(solo_lectura.v) if parentesis.search(t)]

    def test_la_ventana_no_da_veredicto_ni_juzga_contra_una_tolerancia(self, solo_lectura):
        """DA-83 (6): el mensual es solo informativo. La ventana dice las medidas; el unico «no» es el de la regla de guardar (otro asunto: D.1b)."""
        textos = " | ".join(todos_los_textos(solo_lectura.v))
        assert not re.search(r"\b(?:No cumple|Cumple|cumple|fuera de tolerancia|dentro de tolerancia)\b", textos)

    def test_cada_tabla_dice_sus_unidades_en_la_cabecera(self, solo_lectura):
        v = solo_lectura.v
        for tabla in (v.tabla_perfiles, v.tabla_barridos):
            cabeceras = [tabla.horizontalHeaderItem(c).text() for c in range(tabla.columnCount())]
            assert any("[mm]" in c for c in cabeceras)
        cabeceras = [v.tabla_barridos.horizontalHeaderItem(c).text() for c in range(v.tabla_barridos.columnCount())]
        assert cabeceras == ["Capa", "Eje", "Estado", "Bandas", "Bandas medidas", "Media [mm]", "Mediana [mm]", "Desviación [mm]", "Corte central [mm]", "Corte central menos mediana [mm]"], \
            "cada medida en milimetros lo dice en su cabecera (las escribe la prueba a mano)"
        assert all(texto.endswith("[mm]") or texto.endswith("[°]") for texto in (f[0] for f in texto_de_la_tabla(v.tabla_cuadratura) if "Ángulo" not in f[0] or "[°]" in f[0]))


def test_zz_la_ventana_compartida_no_cambio_durante_el_modulo(solo_lectura):
    """La ultima prueba del archivo: ninguna de las que MIRABAN la ventana compartida la cambio (la huella es la del momento de crearla)."""
    ahora, antes = huella(solo_lectura.v), solo_lectura.huella_al_crear
    cambios = [(clave, a, b) for clave in antes for a, b in [(antes[clave], ahora[clave])] if a != b]
    detalle = []
    for clave, a, b in cambios:
        if isinstance(a, list):
            detalle += [(clave, i, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y]
        else:
            detalle.append((clave, a, b))
    assert not cambios and not solo_lectura.avisos, detalle
