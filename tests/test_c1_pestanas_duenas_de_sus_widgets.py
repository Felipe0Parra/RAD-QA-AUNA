"""C.1 (PLAN_HANDOFF_IMAGENES_22-09.md): los widgets de resultados pertenecen a la pestaña, no al objeto.

Antes, `_crear_nueva_tab` dejaba el lienzo, la barra de herramientas y el texto de resultados de la ÚLTIMA pestaña creada
en tres atributos únicos de la pantalla (`canvas_resultados`, `toolbar_tac`, `resultados_texto`), y todo el análisis
escribía ahí: en la pestaña equivocada si el físico había cambiado de pestaña, en un widget destruido si la había
cerrado, y con `AttributeError: 'QTableWidget' object has no attribute 'setText'` si el resultado anterior había
convertido el texto en una tabla. Son el mismo puntero.

Estas pruebas manejan la pantalla como el físico -- crean pestañas con el combo, cambian entre ellas, las cierran y
corren el análisis con el punto de entrada de producción (`imagen_dicom_cargada`, `try_actualizar_linealidad_ct`) --,
y miran dónde cayó el resultado buscándolo en el árbol de Qt, sin pasar por ningún atributo de la pantalla: así valen
igual antes y después del cambio.
"""
import ast
import types
from pathlib import Path

import numpy as np
import pytest
from PyQt5 import sip
from PyQt5.QtWidgets import QLabel, QTableWidget, QTableWidgetItem

from _formularios_imagenes import FORMULARIOS, app, bd_temporal, iniciar, sin_dialogos  # noqa: F401

RAIZ = Path(__file__).resolve().parent.parent
PANTALLA = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "tac_mensual.py"
SEISCIENTOS = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "seiscientos_mensual.py"

UNIFORMIDAD = "Uniformidad y Ruido"
LINEALIDAD = "Linealidad del CT"
TAMANO = "Tamaño de Pixel"
HU_LINEALIDAD = [-1000.0, -95.0, -20.0, 4.0, 110.0, 340.0, 1010.0]     # 7 materiales, crecientes


# ---------------------------------------------------------------------------
# La pantalla y lo que el físico le hace
# ---------------------------------------------------------------------------

def _pantalla(clave):
    """Como después de pulsar "Iniciar": el formulario construido y el combo de resultados conectado a `createTab`."""
    constructor, _equipo, _hoja = FORMULARIOS[clave]
    obj = iniciar(constructor())
    obj.button_click()
    obj.criterios_por_categoria = {}
    return obj


def _ver(obj, texto):
    """El físico elige `texto` en el combo de resultados."""
    obj.graficar.setCurrentText(texto)


def _tab(obj, texto):
    """El widget de la pestaña titulada `texto`, buscado en el QTabWidget (no en ningún atributo de la pantalla)."""
    for i in range(obj.tab_widget.count()):
        if obj.tab_widget.tabText(i) == texto:
            return obj.tab_widget.widget(i)
    return None


def _indice(obj, texto):
    return next(i for i in range(obj.tab_widget.count()) if obj.tab_widget.tabText(i) == texto)


def _titulos(obj):
    return [obj.tab_widget.tabText(i) for i in range(obj.tab_widget.count())]


def _tablas(tab):
    return tab.findChildren(QTableWidget)


def _textos(tab):
    return [t.text() for t in tab.findChildren(QLabel)]


def _fantoma_uniforme():
    """Agua uniforme en un disco de 75 mm de radio (el Catphan 504) sobre aire: lo justo para que `uniformidad` corra
    entera, con el detector de geometría (D.0) sobre el HU."""
    n, tam_px = 512, 0.5
    yy, xx = np.mgrid[:n, :n]
    r_mm = np.hypot(yy - n / 2, xx - n / 2) * tam_px
    hu = np.where(r_mm <= 75.0, 0.0, -1000.0).astype(np.float32)
    grafica = (np.clip(hu + 200.0, 0, 400) / 400.0 * 255.0).astype(np.uint8)
    return hu, grafica, tam_px


def _correr_uniformidad(obj):
    """El físico elige el corte de uniformidad: el punto de entrada de producción de todo el análisis."""
    obj.visualizador_principal = types.SimpleNamespace(vol=types.SimpleNamespace(kv=120, ma=100, espesor_corte=2.0))
    visible = types.SimpleNamespace(isVisible=lambda: True)
    obj.pruebas_categorias = {"uniformidad_ruido": visible}
    obj.imagen_dicom_cargada(*_fantoma_uniforme())


def _correr_linealidad(obj):
    """Los HU de los siete materiales llegan y se ajusta la linealidad (lo que hace la pantalla al cargar los CT)."""
    for fila, valor in enumerate(HU_LINEALIDAD):
        obj.tabla_linealidad_ct.setItem(fila, 5, QTableWidgetItem(f"{valor:.1f}"))
    return obj.try_actualizar_linealidad_ct()


def _guardar(tab):
    """Los botones de guardado de una pestaña."""
    from PyQt5.QtWidgets import QPushButton
    return [b for b in tab.findChildren(QPushButton) if "Guardar" in b.text()]


def _ejes_dibujados(tab):
    """Cuántos ejes tiene el lienzo (la figura de matplotlib) de la pestaña: lo que el análisis dibujó en él."""
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
    (lienzo,) = tab.findChildren(FigureCanvasQTAgg)
    return len(lienzo.figure.axes)


def _hay_linealidad(tab):
    """El texto del ajuste ("Ecuación de la recta: HU = ...") está en la pestaña. No vale buscar "Linealidad": el título
    de la pestaña ("Resultados de Linealidad del CT") ya lo dice sin haber corrido nada."""
    return any("Ecuación de la recta" in t for t in _textos(tab))


CLAVES = sorted(FORMULARIOS)


# ---------------------------------------------------------------------------
# 1. LOS CINCO ESCENARIOS DEL PLAN (cada uno rojo contra el código anterior)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", CLAVES)
def test_a_el_resultado_cae_en_la_pestana_que_se_analiza_aunque_haya_otra_creada_despues(app, bd_temporal, clave):
    """Uniformidad se crea primero, linealidad después; el físico vuelve a uniformidad y analiza: la tabla es de
    uniformidad. Antes, los punteros seguían en la última pestaña creada y la tabla caía en la de linealidad."""
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    _ver(obj, LINEALIDAD)
    _ver(obj, UNIFORMIDAD)                                    # existente: solo se activa
    _correr_uniformidad(obj)
    assert len(_tablas(_tab(obj, UNIFORMIDAD))) == 1, "la tabla de uniformidad no está en la pestaña de uniformidad"
    assert _tablas(_tab(obj, LINEALIDAD)) == [], "la tabla cayó en la pestaña de linealidad"
    assert obj.tab_widget.currentIndex() == _indice(obj, UNIFORMIDAD)
    assert _ejes_dibujados(_tab(obj, UNIFORMIDAD)) > 0, "el análisis no dibujó en el lienzo de su pestaña"
    assert _ejes_dibujados(_tab(obj, LINEALIDAD)) == 0, "el análisis dibujó en el lienzo de otra pestaña"


@pytest.mark.parametrize("clave", CLAVES)
def test_b_un_texto_despues_de_una_tabla_no_revienta(app, bd_temporal, clave):
    """El resultado de uniformidad convierte el texto en tabla; luego se ajusta la linealidad, que escribe TEXTO. Antes
    el puntero seguía siendo la tabla de la otra pestaña: `AttributeError ... 'setText'` y el ajuste devolvía None."""
    obj = _pantalla(clave)
    _ver(obj, LINEALIDAD)
    _ver(obj, UNIFORMIDAD)                                    # la última creada
    _correr_uniformidad(obj)
    assert len(_tablas(_tab(obj, UNIFORMIDAD))) == 1
    resultado = _correr_linealidad(obj)
    assert resultado is not None, "el ajuste de linealidad no corrió"
    assert _hay_linealidad(_tab(obj, LINEALIDAD)), "el texto de la linealidad no llegó a su pestaña"
    assert not _hay_linealidad(_tab(obj, UNIFORMIDAD)), "el texto de la linealidad cayó en la pestaña de uniformidad"


@pytest.mark.parametrize("clave", CLAVES)
def test_c_cerrar_una_pestana_y_analizar_de_nuevo_la_devuelve_con_su_resultado(app, bd_temporal, clave):
    """El físico cierra la pestaña que estaba viendo (el combo sigue diciendo lo mismo) y vuelve a analizar. Antes el
    combo no cambiaba de texto, no se creaba pestaña y el resultado se escribía en la cerrada: no se veía nada."""
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    obj.closeTab(_indice(obj, UNIFORMIDAD))
    assert UNIFORMIDAD not in _titulos(obj)
    _correr_uniformidad(obj)
    assert UNIFORMIDAD in _titulos(obj), "el análisis no volvió a abrir la pestaña que se cerró"
    assert len(_tablas(_tab(obj, UNIFORMIDAD))) == 1
    assert obj.tab_widget.currentIndex() == _indice(obj, UNIFORMIDAD)
    assert _guardar(_tab(obj, UNIFORMIDAD)), "la pestaña reabierta no tiene su botón de guardado"


@pytest.mark.parametrize("clave", CLAVES)
def test_d_cerrar_una_pestana_no_desvia_lo_que_se_escribe_en_otra(app, bd_temporal, clave):
    """Linealidad primero, uniformidad después; se cierra uniformidad y se ajusta la linealidad. Antes el texto iba al
    widget de la pestaña cerrada y la de linealidad se quedaba vacía."""
    obj = _pantalla(clave)
    _ver(obj, LINEALIDAD)
    _ver(obj, UNIFORMIDAD)
    obj.closeTab(_indice(obj, UNIFORMIDAD))
    resultado = _correr_linealidad(obj)
    assert resultado is not None
    assert _hay_linealidad(_tab(obj, LINEALIDAD)), "el texto no llegó a la pestaña de linealidad"
    assert _ejes_dibujados(_tab(obj, LINEALIDAD)) > 0, "el ajuste no dibujó en el lienzo de su pestaña"


@pytest.mark.parametrize("clave", CLAVES)
def test_e_una_pestana_destruida_no_deja_un_puntero_por_el_que_escribir(app, bd_temporal, clave):
    """El widget de la pestaña se destruye (lo que hace `limpiar_recursos` con `deleteLater`) sin pasar por el cierre
    del QTabWidget. Antes: `RuntimeError: wrapped C/C++ object ... has been deleted` en la siguiente escritura."""
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    sip.delete(_tab(obj, UNIFORMIDAD))
    _correr_uniformidad(obj)
    assert UNIFORMIDAD in _titulos(obj)
    assert len(_tablas(_tab(obj, UNIFORMIDAD))) == 1


@pytest.mark.parametrize("clave", ["tomografo", "hc_mensual"])
def test_una_pestana_destruida_se_retira_del_registro_y_no_se_entrega(app, bd_temporal, clave):
    """Un widget muerto no puede quedar en `dynamic_tabs`: cualquiera que recorra el registro (`limpiar_recursos`) lo
    llamaría con `deleteLater` y reventaría a mitad de la limpieza."""
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    sip.delete(_tab(obj, UNIFORMIDAD))
    assert obj._widgets_de(UNIFORMIDAD) is None
    assert UNIFORMIDAD not in obj.dynamic_tabs


@pytest.mark.parametrize("clave", ["tomografo", "hc_mensual"])
def test_el_combo_reabre_una_pestana_destruida(app, bd_temporal, clave):
    """Elegir en el combo una pestaña cuyo widget ya murió la vuelve a crear (antes: `RuntimeError` al activarla)."""
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    sip.delete(_tab(obj, UNIFORMIDAD))
    _ver(obj, LINEALIDAD)
    _ver(obj, UNIFORMIDAD)
    assert UNIFORMIDAD in _titulos(obj)
    assert not sip.isdeleted(_tab(obj, UNIFORMIDAD))
    assert obj.tab_widget.currentIndex() == _indice(obj, UNIFORMIDAD)


@pytest.mark.parametrize("clave", ["tomografo", "hc_mensual"])
def test_el_destino_del_resultado_puede_ser_texto_o_tabla_en_cualquier_orden(app, bd_temporal, clave):
    """El que escribe no sabe qué hay hoy en la ranura de resultados: tabla, texto, tabla, texto..."""
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    tab = _tab(obj, UNIFORMIDAD)
    obj._escribir_resultado(UNIFORMIDAD, QTableWidget())
    assert len(_tablas(tab)) == 1
    obj._escribir_resultado(UNIFORMIDAD, "solo texto")
    assert _tablas(tab) == [] and "solo texto" in _textos(tab)
    obj._escribir_resultado(UNIFORMIDAD, QTableWidget())
    assert len(_tablas(tab)) == 1 and "solo texto" not in _textos(tab)
    obj._escribir_resultado(UNIFORMIDAD, "otro texto")
    assert _tablas(tab) == [] and "otro texto" in _textos(tab) and "solo texto" not in _textos(tab)


@pytest.mark.parametrize("clave", ["tomografo", "hc_mensual"])
def test_texto_sobre_texto_reutiliza_la_misma_etiqueta(app, bd_temporal, clave):
    """Escribir texto donde ya hay texto no cambia el widget: la etiqueta con la que nace la pestaña es la que recibe
    la reconstrucción desde la BD (`GestorReconstruccion`, 50 ms después de crearla) y no se le puede quitar."""
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    etiqueta = obj._widgets_de(UNIFORMIDAD)['label']
    obj._escribir_resultado(UNIFORMIDAD, "uno")
    obj._escribir_resultado(UNIFORMIDAD, "dos")
    assert obj._widgets_de(UNIFORMIDAD)['resultados'].layout().itemAt(0).widget() is etiqueta
    assert etiqueta.text() == "dos"


@pytest.mark.parametrize("clave", ["tomografo", "hc_mensual"])
def test_los_botones_de_guardado_van_a_la_pestana_de_la_prueba(app, bd_temporal, clave):
    """Con la pestaña de OTRA prueba a la vista, el botón de guardado de uniformidad va a la pestaña de uniformidad."""
    obj = _pantalla(clave)
    obj._crear_nueva_tab(UNIFORMIDAD)                   # sin botones (los agrega `createTab`)
    obj._crear_nueva_tab(LINEALIDAD)                    # queda a la vista
    antes = len(_guardar(_tab(obj, LINEALIDAD)))
    obj._agregar_botones_guardado_post_analisis("uniformidad_ruido")
    assert len(_guardar(_tab(obj, UNIFORMIDAD))) == 1, "la pestaña de uniformidad no recibió su botón de guardado"
    assert len(_guardar(_tab(obj, LINEALIDAD))) == antes, "el botón cayó en la pestaña que estaba a la vista"


@pytest.mark.parametrize("clave", ["tomografo", "hc_mensual"])
def test_el_combo_sigue_al_resultado_que_se_ve(app, bd_temporal, clave):
    """El combo de "Ver resultados de..." dice qué prueba se está viendo: al analizar otra, cambia con la pestaña."""
    obj = _pantalla(clave)
    _ver(obj, LINEALIDAD)
    _correr_uniformidad(obj)
    assert obj.graficar.currentText() == UNIFORMIDAD
    assert obj.tab_widget.currentIndex() == _indice(obj, UNIFORMIDAD)


# ---------------------------------------------------------------------------
# 2. LO QUE YA FUNCIONABA Y NO DEBE ROMPERSE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", CLAVES)
def test_repetir_el_analisis_reemplaza_la_tabla_no_la_acumula(app, bd_temporal, clave):
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    _correr_uniformidad(obj)
    _correr_uniformidad(obj)
    assert len(_tablas(_tab(obj, UNIFORMIDAD))) == 1


@pytest.mark.parametrize("clave", CLAVES)
def test_el_criterio_del_equipo_se_muestra_en_la_pestana_analizada_y_solo_en_ella(app, bd_temporal, clave):
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    _ver(obj, LINEALIDAD)
    _correr_uniformidad(obj)
    paneles = {t: _tab(obj, t).findChild(QLabel, "criterio_texto") for t in (UNIFORMIDAD, LINEALIDAD)}
    assert paneles[UNIFORMIDAD].text().strip(), "la pestaña de uniformidad no muestra el criterio"
    assert not paneles[LINEALIDAD].text().strip(), "el criterio de uniformidad cayó en la pestaña de linealidad"


@pytest.mark.parametrize("clave", CLAVES)
def test_limpiar_recursos_destruye_las_pestanas_dinamicas_sin_error(app, bd_temporal, clave, capsys):
    obj = _pantalla(clave)
    _ver(obj, UNIFORMIDAD)
    _ver(obj, LINEALIDAD)
    obj.limpiar_recursos()
    assert obj.dynamic_tabs == {}
    assert "Error al limpiar recursos" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 3. LA CLASE DE ERROR, CERRADA (censo del código de producción)
# ---------------------------------------------------------------------------

PUNTEROS_SUELTOS = {"canvas_resultados", "toolbar_tac", "resultados_texto", "criterio_texto"}


def _fuentes_de_produccion():
    for carpeta in ("ui", "data", "models", "services", "analisisImagenes"):
        for ruta in (RAIZ / carpeta).rglob("*.py"):
            yield ruta


def test_ningun_archivo_de_produccion_guarda_los_widgets_de_una_pestana_en_el_objeto():
    """Ningún `self.<puntero>` ni `obj.<puntero>` en producción: el único camino a un widget de resultados es la pestaña."""
    sueltos = []
    for ruta in _fuentes_de_produccion():
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Attribute) and nodo.attr in PUNTEROS_SUELTOS:
                sueltos.append((str(ruta.relative_to(RAIZ)), nodo.lineno, nodo.attr))
    assert not sueltos, sueltos


def test_la_pantalla_no_le_pide_a_nadie_la_pestana_actual_para_escribir():
    """`currentWidget()` era la otra forma de escribir "donde toque": el que escribe pide la pestaña por su nombre."""
    arbol = ast.parse(PANTALLA.read_text(encoding="utf-8"))
    usos = [n.lineno for n in ast.walk(arbol) if isinstance(n, ast.Attribute) and n.attr == "currentWidget"]
    assert not usos, usos


def _pestanas_pedidas():
    """Los nombres de pestaña que pide el código de producción: constantes de `pestana = "..."` y argumentos literales
    de los cuatro accesos."""
    arbol = ast.parse(PANTALLA.read_text(encoding="utf-8"))
    accesos = {"_abrir_pestana", "_widgets_de", "_escribir_resultado", "_canvas_de"}
    nombres = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "pestana" for t in n.targets) \
                and isinstance(n.value, ast.Constant):
            nombres.add(n.value.value)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) in accesos and n.args \
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            nombres.add(n.args[0].value)
    return nombres


def test_todo_nombre_de_pestana_que_pide_el_codigo_existe_en_el_combo_y_en_el_mapeo():
    """Un nombre mal escrito crearía una pestaña que ningún combo ni mapeo conoce (y el resultado quedaría donde nadie
    lo busca)."""
    from ui.paginasControles.PruebasMensuales.tac_mensual import CategoriasMapping
    del_mapeo = {info["pestaña"] for info in CategoriasMapping.MAPEO_COMPLETO.values()}
    pedidas = _pestanas_pedidas()
    assert pedidas, "el censo no encontró ninguna pestaña pedida: el detector está roto"
    assert pedidas <= del_mapeo, pedidas - del_mapeo


@pytest.mark.parametrize("clave", ["tomografo"])
def test_el_combo_y_el_mapeo_hablan_de_las_mismas_pestanas(app, bd_temporal, clave):
    from ui.paginasControles.PruebasMensuales.tac_mensual import CategoriasMapping
    obj = _pantalla(clave)
    combo = {obj.graficar.itemText(i) for i in range(obj.graficar.count())} - {"Ver resultados de..."}
    assert combo == {info["pestaña"] for info in CategoriasMapping.MAPEO_COMPLETO.values()}
