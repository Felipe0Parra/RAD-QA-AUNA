"""E.3 (PLAN_ANALISIS_PELICULAS_08-10.md, DP-163, 27-10): el cuadro «Pelicula virgen» se puede achicar y maximizar.

CAUSA (medida el 27-10 sin pantalla, `logs/E3/dialogo_en_head.log` y `reproducir_head.log` del anexo). `DialogoPeliculaVirgen` (`ui/paginasControles/PruebasMensuales/placa_mensual.py`) no baja de 626 x 885 px: su
columna derecha suma tres tablas de 150, 150 y 200 px de alto minimo y cinco recuadros de texto con ajuste de linea, sin un area que se desplace (su `sizeHint` es de 1212 x 1275), y como `QDialog` no trae boton
de maximizar. Lo encontro el fisico en el rebuild del 26-10: «que primero se le reduzca la resolucion minima y que se pueda volver de pantalla completa con el boton ese de pantalla completa».

Que fija este archivo (todo por el cuadro REAL, construido sin `exec_()` y cerrado con la receta de la Trampa 9; con la virgen sintetica valida, con una rechazada y, si la carpeta de peliculas esta, con
EPSON179 [valida] y EPSON178 [rechazada por el rango]):
  1. EL TAMANO MINIMO. El `minimumSizeHint` del cuadro es de 800 x 600 o menos (E3-D4: cabe en una pantalla de 1024 x 768) y pedir 800 x 600 a un cuadro ya mostrado da 800 x 600 (en HEAD da 800 x 885).
  2. LA BANDERA. Trae `WindowMaximizeButtonHint`, NO trae `WindowMinimizeButtonHint` (E3-D1: es modal; minimizado dejaria la app bloqueada sin ninguna ventana a la vista) y sigue siendo un `QDialog` de tipo
     dialogo. `showMaximized()` lo deja maximizado y `showNormal()` lo devuelve (offscreen maximiza con o sin la bandera: el boton de la barra de titulo es de cada sistema y se mira en el rebuild).
  3. EL TAMANO INICIAL. Se abre con `_tamano_inicial()`, la regla de la ventana del analisis (E3-D3), sin literales: con otro valor de la regla se abre con ESE tamano, tambien tras mostrarse.
  4. QUE SE DESPLAZA Y QUE NO (E3-D2). El resumen, las tres tablas con sus titulos, los recuadros y los avisos van dentro de UN area que se desplaza; la imagen con su barra, la orientacion declarada con su
     rotulo y los botones «Guardar como referencia» y «Cerrar» quedan FUERA de ella.
  5. A 800 x 600: la orientacion y los dos botones se ven enteros dentro del cuadro; lo que no cabe se desplaza (la barra vertical tiene recorrido) y se ALCANZA: arriba se ve el principio del resumen y
     abajo el final de la procedencia; las tablas conservan su alto minimo (150, 150 y 200 px: el area las desplaza, no las aplasta).
  6. EL AREA ES REDIMENSIONABLE: en un cuadro grande el contenido toma todo el area (ni barras ni huecos).
  7. LO QUE NO CAMBIA: titulo, textos de las tres tablas, de cada recuadro y de los avisos, los menus de la orientacion, los textos y el estado de los botones son los que dan las funciones del dibujo y la
     referencia (el oraculo no es el cuadro); «Guardar como referencia» acepta el cuadro (solo si la referencia es valida) con la orientacion declarada y «Cerrar» lo rechaza.

Trampa 2 (la fixture `dialogos` parcha todo `QMessageBox` y todo `exec_`: el cuadro es modal y aqui nunca se ejecuta), Trampa 9 (`cerrar`), Trampa 10 (ningun `lru_cache`: los resultados caros son fixtures de modulo
y nadie los muta; un control que solo vale para las peliculas reales se salta con HI-0 como el de OD.1, nunca con un `skip` de otra clase). Ningun texto lleva simbolos de correcto o incorrecto (DA-18)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QScrollArea

import _corpus
import _placa_mensual_sintetica as gen
from _e1_ayudas import FECHA_DE_PRUEBA, _cursor_limpio, app, cerrar, dialogos, dibujo_mod, escaneo_virgen, parametros, pel, sin_simbolos, texto_de_la_tabla, ventana_mod  # noqa: F401  (fixtures)

LIMITE = (800, 600)                  # E3-D4: la garantia del cuadro es «baja a 800 x 600 o menos»
GRANDE = (1600, 1500)                # mas alto que lo que pide el contenido del caso con mas texto (la rechazada: ~1105 px de contenido): el area no necesita barras
TITULOS_DE_LAS_TABLAS = ("Valor de la película virgen por capa (es el piso)", "Uniformidad y ruido", "Comprobaciones")
ROTULO_DE_LA_ORIENTACION = "Orientación de la película virgen:"
ALTOS_MINIMOS = {"tabla_valores": 150, "tabla_uniformidad": 150, "tabla_pruebas": 200}      # los que fija `__init__` desde antes de E.3 (no cambian)
REALES = {"EPSON179": ("VIRGEN_EPSON179", True), "EPSON178": ("VIRGEN_EPSON178", False)}      # nombre -> (clave del corpus, ¿la referencia es valida?)


# ------------------------------------------------------------------------------------------------------ los casos

@pytest.fixture(scope="module")
def irradiada():
    """Una pelicula IRRADIADA de la sintetica de PF.0 (independiente del motor), que se usa como si fuera la virgen: el rango de una pelicula sin irradiar la rechaza (el caso de EPSON178)."""
    return gen.generar("png", variante="A", seed=1)


@pytest.fixture(scope="module")
def virgen_rechazada(irradiada):
    referencia = pel().piso_de_pelicula_virgen(irradiada.datos, parametros(), "irradiada_como_virgen.png", fecha_calculo=FECHA_DE_PRUEBA)
    assert referencia.estado.startswith("no válida"), referencia.estado
    return referencia


@pytest.fixture(scope="module", params=["valida", "rechazada"])
def caso(request, escaneo_virgen, irradiada, virgen_rechazada):
    """La referencia y los bytes de la virgen sintetica valida y de la rechazada: nadie las muta."""
    if request.param == "valida":
        return SimpleNamespace(nombre="sintetica valida", referencia=escaneo_virgen.referencia, datos=escaneo_virgen.datos, valida=True)
    return SimpleNamespace(nombre="sintetica rechazada", referencia=virgen_rechazada, datos=irradiada.datos, valida=False)


@pytest.fixture(scope="module", params=sorted(REALES))
def caso_real(request):
    """EPSON179 (valida) o EPSON178 (rechazada por el rango), los TIFF de 99 MB que el fisico escaneo el 21-10: salta (HI-0) si la carpeta de peliculas no los tiene; la regla de PR.0 FALLA si la carpeta existe y
    a la declarada le falta el archivo."""
    clave, valida = REALES[request.param]
    ruta = _corpus.pelicula(clave)
    if ruta is None:
        pytest.skip(f"HI-0: {request.param} no esta en {_corpus.PELICULAS_RAIZ}")
    datos = Path(ruta).read_bytes()
    referencia = pel().piso_de_pelicula_virgen(datos, parametros(), f"{request.param}.TIF", fecha_calculo=FECHA_DE_PRUEBA)
    assert (referencia.estado == "ok") == valida, referencia.estado
    return SimpleNamespace(nombre=request.param, referencia=referencia, datos=datos, valida=valida)


def _abrir(caso):
    """El cuadro como lo abre la ventana (sin `exec_`): `DialogoPeliculaVirgen(referencia, datos, existente, parent)`."""
    return ventana_mod().DialogoPeliculaVirgen(caso.referencia, caso.datos, None, None)


@pytest.fixture
def cuadro(app, caso, dialogos):
    c = _abrir(caso)
    yield c
    cerrar(c)


@pytest.fixture
def cuadro_real(app, caso_real, dialogos):
    c = _abrir(caso_real)
    yield c
    cerrar(c)


# ------------------------------------------------------------------------------------------------------ lo que se mira del cuadro

def _del_area(c):
    """Lo que debe desplazarse: el resumen, las tres tablas, los recuadros y los avisos."""
    return [c.resumen, c.tabla_valores, c.tabla_uniformidad, c.nota_uniformidad, c.caja_de_la_pelicula, c.tabla_pruebas, c.avisos, c.procedencia]


def _fijos(c):
    """Lo que siempre debe estar a la vista: la orientacion declarada y los dos botones."""
    return [c.selector_orientacion, c.boton_guardar, c.boton_cerrar]


def _etiqueta(c, texto):
    etiquetas = [e for e in c.findChildren(QLabel) if e.text() == texto]
    assert len(etiquetas) == 1, f"debe haber exactamente una etiqueta «{texto}» y hay {len(etiquetas)}"
    return etiquetas[0]


def _el_area(c):
    """El UNICO `QScrollArea` que contiene al resumen (compuerta: si no hay area, esta funcion cae con su motivo y no con un error de otra cosa)."""
    areas = [a for a in c.findChildren(QScrollArea) if a.isAncestorOf(c.resumen)]
    assert len(areas) == 1, f"el resumen debe estar dentro de UN area que se desplaza y esta dentro de {len(areas)}"
    return areas[0]


def _rect_en(c, w):
    """El rectangulo de `w` en coordenadas del cuadro. Un widget que no es descendiente del cuadro (un boton que ningun layout agrego) no se mapea: `mapTo` aborta el proceso de Qt, no lanza; cae con su motivo."""
    assert c.isAncestorOf(w), f"{w.__class__.__name__} ({getattr(w, 'text', lambda: '')()!r}) no esta dentro del cuadro: ningun layout lo agrego"
    return QRect(w.mapTo(c, QPoint(0, 0)), w.size())


def _afirmar_barras_a_la_vista(c, area):
    """E3-R1-AM-02 (ronda 1 de revision, 27-10): una barra con recorrido que no se ve esconde lo que no cabe SIN avisar que hay mas (Qt mueve la barra con `setValue` aunque este oculta). Toda barra del area con recorrido
    esta visible y entera dentro del cuadro."""
    for nombre, barra in (("vertical", area.verticalScrollBar()), ("horizontal", area.horizontalScrollBar())):
        if barra.maximum() > 0:
            assert barra.isVisible(), f"la barra {nombre} del area tiene recorrido ({barra.maximum()}) y no se ve: el fisico no sabria que hay mas contenido"
            assert c.rect().contains(_rect_en(c, barra)), f"la barra {nombre} del area queda fuera del cuadro"


def _mostrar(c, ancho, alto):
    """Muestra el cuadro (sin `exec_`) y le pide ese tamano; deja que Qt reparta el layout."""
    c.show()
    QApplication.processEvents()
    c.resize(ancho, alto)
    QApplication.processEvents()
    QApplication.processEvents()
    assert (c.width(), c.height()) == (ancho, alto), f"el cuadro no pudo tomar el tamano pedido: se pidio {ancho} x {alto} y quedo en {c.width()} x {c.height()} (su minimo es {c.minimumSizeHint().width()} x {c.minimumSizeHint().height()})"


# ====================================================================================================== 1. el tamano minimo

class TestElTamanoMinimo:
    def test_el_cuadro_baja_a_800_por_600_o_menos(self, cuadro, caso):
        m = cuadro.minimumSizeHint()
        assert m.width() <= LIMITE[0] and m.height() <= LIMITE[1], f"el minimo del cuadro ({caso.nombre}) es {m.width()} x {m.height()} y debe ser de {LIMITE[0]} x {LIMITE[1]} o menos"
        layout = cuadro.layout().minimumSize()
        assert layout.width() <= LIMITE[0] and layout.height() <= LIMITE[1], f"el minimo del layout es {layout.width()} x {layout.height()}"
        assert cuadro.tabla_pruebas.rowCount() == len(caso.referencia.pruebas) > 0, "compuerta de no vacuidad: el cuadro trae sus comprobaciones y aun asi baja de tamano"

    def test_pedir_800_por_600_a_un_cuadro_mostrado_da_800_por_600(self, cuadro, caso):
        _mostrar(cuadro, *LIMITE)
        assert (cuadro.width(), cuadro.height()) == LIMITE, f"se pidio {LIMITE} y el cuadro ({caso.nombre}) quedo en {cuadro.width()} x {cuadro.height()}"

    def test_pedir_un_tamano_menor_que_el_de_antes_tambien_se_respeta(self, cuadro):
        """Un tamano que no es el 800 x 600 de la garantia (ni cercano al minimo medido): el cuadro se achica HASTA lo que se le pide, no hasta un piso que cae justo en 800 x 600."""
        _mostrar(cuadro, 700, 500)
        assert (cuadro.width(), cuadro.height()) == (700, 500), f"quedo en {cuadro.width()} x {cuadro.height()}"


# ====================================================================================================== 2. la bandera de maximizar

class TestLaBanderaDeMaximizar:
    def test_trae_el_boton_de_maximizar_y_no_el_de_minimizar_y_sigue_siendo_un_dialogo(self, cuadro):
        banderas = cuadro.windowFlags()
        assert banderas & Qt.WindowMaximizeButtonHint, "el cuadro no trae el boton de maximizar"
        assert not banderas & Qt.WindowMinimizeButtonHint, "E3-D1: el cuadro es modal, no trae el boton de minimizar"
        assert (banderas & Qt.WindowType_Mask) == Qt.Dialog and isinstance(cuadro, QDialog), "sigue siendo un dialogo"

    def test_conserva_las_demas_banderas_el_boton_de_cerrar_incluido(self, cuadro):
        """E3-R1-AM-01 (ronda 1 de revision, 27-10): E.3 SUMA una bandera, no reescribe las del cuadro. Reescribirlas con el idioma habitual (`setWindowFlags(Qt.Dialog | Qt.WindowMaximizeButtonHint)`) deja el cuadro
        con maximizar y sin el boton de cerrar ni la ayuda contextual y NINGUNA otra prueba de este archivo lo ve. Las banderas, salvo la de maximizar, son las de un `QDialog` comun de esta plataforma (el oraculo no
        es el cuadro) y el boton de cerrar esta."""
        comun = QDialog()
        try:
            esperadas = int(comun.windowFlags()) & ~int(Qt.WindowMaximizeButtonHint)
        finally:
            cerrar(comun)
        assert esperadas & int(Qt.WindowCloseButtonHint), "compuerta de no vacuidad: un dialogo comun trae el boton de cerrar"
        banderas = int(cuadro.windowFlags())
        assert banderas & int(Qt.WindowCloseButtonHint), "el cuadro perdio el boton de cerrar"
        perdidas, nuevas = esperadas & ~banderas, banderas & ~esperadas & ~int(Qt.WindowMaximizeButtonHint)
        assert banderas & ~int(Qt.WindowMaximizeButtonHint) == esperadas, f"las banderas del cuadro, salvo la de maximizar, deben ser las de un dialogo comun: pierde {perdidas:#x} y suma {nuevas:#x}"

    def test_maximizado_se_ve_entero_y_se_devuelve_al_tamano_de_antes(self, cuadro):
        cuadro.show()
        QApplication.processEvents()
        antes = (cuadro.width(), cuadro.height())
        cuadro.showMaximized()
        QApplication.processEvents()
        QApplication.processEvents()
        assert cuadro.isMaximized()
        for w in _fijos(cuadro):
            assert w.isVisibleTo(cuadro) and cuadro.rect().contains(_rect_en(cuadro, w)), f"maximizado, {w.__class__.__name__} no se ve entero"
        cuadro.showNormal()
        QApplication.processEvents()
        QApplication.processEvents()
        assert not cuadro.isMaximized()
        assert (cuadro.width(), cuadro.height()) == antes, f"E3-R1-AM-03: al volver de maximizado el cuadro debe quedar en el tamano de antes {antes} y quedo en {cuadro.width()} x {cuadro.height()}"


# ====================================================================================================== 3. el tamano inicial

class TestElTamanoInicial:
    def test_se_abre_con_el_tamano_inicial_de_la_ventana_del_analisis(self, cuadro):
        esperado = ventana_mod()._tamano_inicial()
        assert (cuadro.width(), cuadro.height()) == esperado, f"se abre en {cuadro.width()} x {cuadro.height()} y la regla de la ventana da {esperado}"
        cuadro.show()
        QApplication.processEvents()
        assert (cuadro.width(), cuadro.height()) == esperado, "al mostrarse, el cuadro conserva su tamano inicial (no se ajusta a su `sizeHint`)"

    @pytest.mark.parametrize("tamano", [(700, 500), (1000, 700)])
    def test_con_otro_valor_de_la_regla_se_abre_con_ese_tamano(self, app, caso, dialogos, monkeypatch, tamano):
        monkeypatch.setattr(ventana_mod(), "_tamano_inicial", lambda: tamano)
        c = _abrir(caso)
        try:
            assert (c.width(), c.height()) == tamano, f"la regla dio {tamano} y el cuadro se abrio en {c.width()} x {c.height()}"
            c.show()
            QApplication.processEvents()
            assert (c.width(), c.height()) == tamano
        finally:
            cerrar(c)


# ====================================================================================================== 4. que se desplaza y que no

class TestQueSeDesplazaYQueNo:
    def test_el_resumen_las_tablas_los_recuadros_y_los_avisos_van_dentro_del_area(self, cuadro):
        area = _el_area(cuadro)
        for w in _del_area(cuadro):
            assert area.isAncestorOf(w), f"{w.objectName() or w.__class__.__name__} ({getattr(w, 'text', lambda: '')()[:40]!r}) debe estar dentro del area que se desplaza"
        for titulo in TITULOS_DE_LAS_TABLAS:
            assert area.isAncestorOf(_etiqueta(cuadro, titulo)), f"el titulo «{titulo}» va con su tabla, dentro del area"
        assert len(_del_area(cuadro)) == 8 and len(set(map(id, _del_area(cuadro)))) == 8, "compuerta de no vacuidad: son ocho piezas distintas"

    def test_la_orientacion_y_los_dos_botones_quedan_fuera_del_area(self, cuadro):
        area = _el_area(cuadro)
        for w in _fijos(cuadro):
            assert not area.isAncestorOf(w), f"{w.__class__.__name__} ({getattr(w, 'text', lambda: '')()!r}) debe quedar fuera del area, siempre a la vista"
        assert not area.isAncestorOf(_etiqueta(cuadro, ROTULO_DE_LA_ORIENTACION)), "el rotulo de la orientacion va con su menu, fuera del area"

    def test_la_imagen_con_su_barra_no_se_desplaza(self, cuadro):
        area = _el_area(cuadro)
        assert not area.isAncestorOf(cuadro.lienzo) and not area.isAncestorOf(cuadro.barra)
        assert cuadro.isAncestorOf(cuadro.lienzo) and cuadro.isAncestorOf(cuadro.barra), "compuerta de no vacuidad: la imagen y su barra estan en el cuadro, solo que fuera del area"


# ====================================================================================================== 5. a 800 x 600

class TestA800Por600:
    def test_la_orientacion_y_los_dos_botones_se_ven_enteros(self, cuadro):
        _mostrar(cuadro, *LIMITE)
        for w in _fijos(cuadro):
            r = _rect_en(cuadro, w)
            assert w.isVisibleTo(cuadro) and r.width() > 0 and r.height() > 0, f"{w.__class__.__name__} ({getattr(w, 'text', lambda: '')()!r}) no se ve"
            assert cuadro.rect().contains(r), f"{w.__class__.__name__} ({getattr(w, 'text', lambda: '')()!r}) queda fuera del cuadro de {LIMITE}: {r} frente a {cuadro.rect()}"

    def test_lo_que_no_cabe_se_desplaza_y_se_alcanza_de_arriba_a_abajo(self, cuadro):
        _mostrar(cuadro, *LIMITE)
        area = _el_area(cuadro)
        barra, vista = area.verticalScrollBar(), area.viewport()
        assert barra.maximum() > 0, "a 800 x 600 la columna de la derecha no cabe entera: la barra debe tener recorrido (compuerta de no vacuidad)"
        _afirmar_barras_a_la_vista(cuadro, area)
        visibles = [w for w in _del_area(cuadro) if w.isVisibleTo(cuadro)]
        assert cuadro.resumen in visibles and cuadro.procedencia in visibles and len(visibles) >= 7
        primero, ultimo = cuadro.resumen, max(visibles, key=lambda w: w.mapTo(area.widget(), QPoint(0, 0)).y())
        barra.setValue(0)
        QApplication.processEvents()
        arriba = primero.mapTo(vista, QPoint(0, 0))
        assert arriba.y() >= 0 and arriba.y() < vista.height(), f"arriba se ve el principio del resumen: {arriba}"
        barra.setValue(barra.maximum())
        QApplication.processEvents()
        abajo = ultimo.mapTo(vista, QPoint(0, 0)).y() + ultimo.height()
        assert 0 < abajo <= vista.height(), f"abajo se ve el final de lo ultimo ({ultimo.text()[:30]!r}): termina en {abajo} y el area mide {vista.height()}"

    def test_las_tablas_conservan_su_alto_minimo_el_area_las_desplaza_y_no_las_aplasta(self, cuadro):
        _mostrar(cuadro, *LIMITE)
        for nombre, minimo in ALTOS_MINIMOS.items():
            tabla = getattr(cuadro, nombre)
            assert tabla.minimumHeight() == minimo, f"{nombre}: el alto minimo que fija `__init__` desde antes de E.3 es {minimo}"
            assert tabla.height() >= minimo, f"{nombre} se aplasta a {tabla.height()} px (su minimo es {minimo})"


# ====================================================================================================== 6. el area es redimensionable

class TestElAreaEsRedimensionable:
    def test_en_un_cuadro_grande_el_contenido_toma_todo_el_area(self, cuadro):
        _mostrar(cuadro, *GRANDE)
        area = _el_area(cuadro)
        assert area.widgetResizable()
        assert area.widget().minimumSizeHint().height() <= area.viewport().height(), "premisa: el cuadro grande le da al contenido todo el alto que pide (lo pide mas el caso con mas texto)"
        assert area.widget().size() == area.viewport().size(), f"el contenido ({area.widget().size()}) no llena el area ({area.viewport().size()})"
        assert area.verticalScrollBar().maximum() == 0 and area.horizontalScrollBar().maximum() == 0, "con espacio de sobra el area no necesita barras"
        assert area.isAncestorOf(cuadro.tabla_pruebas)

    def test_la_tabla_de_comprobaciones_crece_con_el_cuadro(self, cuadro):
        """Con el cuadro grande el area redimensionable le da a la tabla de comprobaciones mas que su alto minimo (el area no deja el contenido en su alto minimo: sin `setWidgetResizable` esta prueba cae)."""
        _mostrar(cuadro, *GRANDE)
        assert cuadro.tabla_pruebas.height() > ALTOS_MINIMOS["tabla_pruebas"], f"a {GRANDE[0]} x {GRANDE[1]} la tabla de comprobaciones mide {cuadro.tabla_pruebas.height()} px"


# ====================================================================================================== 7. lo que no cambia

class TestLoQueNoCambia:
    def test_los_textos_las_tablas_y_el_estado_de_los_botones_son_los_de_siempre(self, cuadro, caso):
        r, d = caso.referencia, dibujo_mod()
        assert cuadro.windowTitle() == "Película virgen"
        assert cuadro.resumen.text() == r.descripcion() and cuadro.resumen.text()
        assert texto_de_la_tabla(cuadro.tabla_valores) == [list(f) for f in d.filas_de_la_virgen(r)] and cuadro.tabla_valores.rowCount() == 4
        assert texto_de_la_tabla(cuadro.tabla_uniformidad) == [list(f) for f in d.filas_de_la_uniformidad(r)] and cuadro.tabla_uniformidad.rowCount() > 0
        assert texto_de_la_tabla(cuadro.tabla_pruebas) == [list(f) for f in d.filas_de_las_pruebas(r)] and cuadro.tabla_pruebas.rowCount() == len(r.pruebas)
        assert cuadro.nota_uniformidad.text() == d.texto_de_la_uniformidad(r)
        assert cuadro.caja_de_la_pelicula.text() == d.texto_de_la_caja_de_la_pelicula(r)
        assert cuadro.procedencia.text() == d.texto_de_la_procedencia(r)
        assert cuadro.avisos.text() == ("Avisos: " + "; ".join(r.avisos) if r.avisos else "") and cuadro.avisos.isVisibleTo(cuadro) == bool(r.avisos)
        assert [cuadro.selector_orientacion.itemText(i) for i in range(cuadro.selector_orientacion.count())] == list(d.ORIENTACIONES_DE_LA_VIRGEN)
        assert (cuadro.boton_guardar.text(), cuadro.boton_cerrar.text()) == ("Guardar como referencia", "Cerrar")
        assert cuadro.boton_guardar.isEnabled() == (r.estado == "ok") == caso.valida and cuadro.boton_cerrar.isEnabled()
        textos = [cuadro.resumen.text(), cuadro.nota_uniformidad.text(), cuadro.caja_de_la_pelicula.text(), cuadro.procedencia.text(), cuadro.avisos.text()]
        assert all(sin_simbolos(t) for t in textos), "DA-18: ningun texto del cuadro lleva simbolos de correcto o incorrecto"

    def test_la_imagen_y_las_regiones_se_siguen_dibujando(self, cuadro, caso):
        assert cuadro.eje.images, "el escaneo se dibuja"
        gids = {a.get_gid() for a in cuadro.eje.get_children()}
        if caso.valida:
            assert "virgen:zona" in gids, "la zona que se midio se ve dibujada sobre el escaneo"

    def test_cerrar_rechaza_el_cuadro_desde_su_sitio_nuevo(self, cuadro):
        assert cuadro.boton_cerrar.isEnabled()
        cuadro.boton_cerrar.click()
        assert cuadro.result() == QDialog.Rejected and not cuadro.guardar_solicitado

    def test_guardar_acepta_el_cuadro_solo_si_la_referencia_es_valida_y_con_la_orientacion_declarada(self, cuadro, caso):
        cuadro.selector_orientacion.setCurrentIndex(1)
        assert cuadro.orientacion_declarada() == dibujo_mod().ORIENTACIONES_DE_LA_VIRGEN[1]
        cuadro.boton_guardar.click()
        if caso.valida:
            assert cuadro.guardar_solicitado and cuadro.result() == QDialog.Accepted
            assert cuadro.referencia_final().procedencia["orientacion_declarada"] == dibujo_mod().ORIENTACIONES_DE_LA_VIRGEN[1]
        else:
            assert not cuadro.boton_guardar.isEnabled() and not cuadro.guardar_solicitado and cuadro.result() != QDialog.Accepted


# ====================================================================================================== 8. las peliculas virgenes REALES (HI-0)

class TestConLasVirgenesReales:
    """La misma garantia con los dos TIFF de 99 MB del 21-10 (textos mas largos, los avisos de EPSON179 y el rechazo por el rango de EPSON178): un solo cuadro por prueba, pues cada uno lee 99 MB."""

    def test_baja_a_800_por_600_con_la_orientacion_y_los_botones_a_la_vista_y_el_resto_en_el_area(self, cuadro_real, caso_real):
        c = cuadro_real
        m = c.minimumSizeHint()
        assert m.width() <= LIMITE[0] and m.height() <= LIMITE[1], f"el minimo del cuadro de {caso_real.nombre} es {m.width()} x {m.height()}"
        assert c.windowFlags() & Qt.WindowMaximizeButtonHint and not c.windowFlags() & Qt.WindowMinimizeButtonHint
        _mostrar(c, *LIMITE)
        assert (c.width(), c.height()) == LIMITE
        area = _el_area(c)
        assert all(area.isAncestorOf(w) for w in _del_area(c)) and not any(area.isAncestorOf(w) for w in _fijos(c))
        assert all(w.isVisibleTo(c) and c.rect().contains(_rect_en(c, w)) for w in _fijos(c))
        assert area.verticalScrollBar().maximum() > 0
        _afirmar_barras_a_la_vista(c, area)

    def test_los_textos_son_los_de_siempre_y_el_cuadro_se_abre_con_la_regla_de_la_ventana(self, cuadro_real, caso_real):
        c, r, d = cuadro_real, caso_real.referencia, dibujo_mod()
        assert (c.width(), c.height()) == ventana_mod()._tamano_inicial()
        assert c.resumen.text() == r.descripcion() and c.procedencia.text() == d.texto_de_la_procedencia(r)
        assert texto_de_la_tabla(c.tabla_valores) == [list(f) for f in d.filas_de_la_virgen(r)]
        assert texto_de_la_tabla(c.tabla_pruebas) == [list(f) for f in d.filas_de_las_pruebas(r)]
        assert c.boton_guardar.isEnabled() == caso_real.valida
