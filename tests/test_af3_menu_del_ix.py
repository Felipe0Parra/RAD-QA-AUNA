"""AF.3: el anual del iX navega «FACTOR SOBRE EL EJE» y «LECTURAS DE LINEALIDAD» con un menú desplegable, cada tabla
lleva un circulito (verde: guardada y sin editar; rojo: sin guardar o editada), la tabla elegida usa todo el alto y
salen las cuñas de electrones, que el formato no tiene. Los dos títulos con menú llevan una flechita. Toda edición del
físico vuelve rojo el circulito, también la corrección a mano de un valor calculado; lo que la app escribe sola, no.
Nada de lo que se guarda cambia.

Las páginas se arman como al pulsar «Iniciar», sobre una base temporal, a 1920 x 980 (una pantalla de 1920 x 1080 sin
las barras). Trampa 2: ningún diálogo real (QMessageBox parchado y QMenu.exec_ prohibido: el menú se abre con popup).
"""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5 import sip
from PyQt5.QtCore import QCoreApplication, QEvent, QObject, QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import (QAbstractButton, QApplication, QLayout, QLineEdit, QMenu, QPushButton, QScrollBar,
                             QTableWidget, QTableWidgetItem, QToolBox)

import ui.paginasControles.PruebasAnuales.ix_anual as ix_anual_mod
import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX
from _formularios_imagenes import app, bd_temporal, sin_dialogos  # noqa: F401  (fixtures)

ENTRADAS = ['encabezado_anual_ix', 'Control anual', 'Iniciar control anual', 'Clinac ix', 'preguntas_anual_ix']
SECCIONES = ["EQUIPOS DE MEDICIÓN", "FACTOR DE CAMPO", "FACTOR DE TRANSMISIÓN", "FACTOR SOBRE EL EJE",
             "CONTROL DE CÁMARAS", "LECTURAS DE LINEALIDAD"]
GRUPOS = {"Linealidad de unidades monitor": ["6 MV", "15 MV", "6 MeV", "9 MeV", "12 MeV", "15 MeV"],
          "Lecturas de factor de campo": ["6 MV", "15 MV"],
          "Lecturas de factor de cono": ["6 MeV", "9 MeV", "12 MeV", "15 MeV"],
          "Lecturas de transmisión de cuñas": ["6 MV", "15 MV"],
          "Tasa de dosis (constancia)": ["6 MV", "15 MV"]}
ENERGIAS = ["6 MV", "15 MV", "6 MeV", "9 MeV", "12 MeV", "15 MeV"]
VERDE, ROJO, FLECHITA = (46, 160, 67), (200, 40, 40), (60, 60, 60)
CON_MENU = ("FACTOR SOBRE EL EJE", "LECTURAS DE LINEALIDAD")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Usuario:
    _nombre = "Fisico Real"


@pytest.fixture(autouse=True)
def sin_menus_modales(monkeypatch):
    """Trampa 2: un menú modal colgaría la suite; el menú de la página se abre con popup()."""
    def _prohibido(*a, **k):
        raise AssertionError("se abrió un menú modal (exec_)")
    monkeypatch.setattr(QMenu, "exec_", _prohibido)
    monkeypatch.setattr(QMenu, "exec", _prohibido)


class _SenalMuda:
    def connect(self, *a):
        pass


class _RelojQuieto:
    """Un QTimer que nunca dispara."""
    def __init__(self, *a, **k):
        self.timeout = _SenalMuda()

    def setSingleShot(self, *a):
        pass

    def start(self, *a):
        pass

    def stop(self):
        pass

    def isActive(self):
        return False

    def deleteLater(self):
        pass


@pytest.fixture
def sin_recalculo_diferido(monkeypatch):
    """Congela el recálculo diferido de la app (300 ms tras cada cambio): la prueba no depende del reloj."""
    monkeypatch.setattr(mensual_mod, "QTimer", _RelojQuieto)


def _bombear():
    for _ in range(4):
        QApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.fixture
def paginas(app, bd_temporal):
    """Páginas del anual del iX con la hoja de estilo de la app (las medidas son las que ve el físico)."""
    anterior = app.styleSheet()
    with open(os.path.join(RAIZ, "resources", "estilo.qss"), encoding="utf-8") as f:
        app.setStyleSheet(f.read())
    hechas = []

    def hacer():
        obj = PruebaAnualIX(user_id=_Usuario())
        obj.fisico1.addItem("Fisico Real", 1)
        obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
        obj.user_id_f1 = "Fisico Real"
        obj.user_id_f2 = None
        obj._iniciar_moviendo_tabla(ENTRADAS)
        obj.resize(1920, 980)
        obj.show()
        _bombear()
        hechas.append(obj)
        return obj
    yield hacer
    for obj in hechas:
        for menu in obj.findChildren(QMenu):
            menu.hide()
        obj.hide()
        obj.close()
        obj.deleteLater()
    _bombear()
    hechas.clear()
    gc.collect()  # Trampa 9: las páginas cerradas se sueltan del todo
    app.setStyleSheet(anterior)


def _caja(obj):
    cajas = obj.findChildren(QToolBox)
    return max(cajas, key=lambda t: sum(1 for i in range(t.count()) if t.itemText(i).isupper()))


def _titulos(caja):
    return [caja.itemText(i) for i in range(caja.count())]


def _seccion(obj, titulo):
    seccion = {"FACTOR SOBRE EL EJE": getattr(obj, "menu_fse", None),
               "LECTURAS DE LINEALIDAD": getattr(obj, "menu_linealidad", None)}[titulo]
    if seccion is None:
        pytest.fail(f"la sección {titulo} no tiene menú desplegable")
    return seccion


def _boton_de_titulo(caja, titulo):
    botones = [b for b in caja.findChildren(QAbstractButton, "qt_toolbox_toolboxbutton", Qt.FindDirectChildrenOnly)
               if b.text() == titulo]
    assert len(botones) == 1, f"el título {titulo} debe ser un botón qt_toolbox_toolboxbutton de la caja principal"
    return botones[0]


def _clic_en_titulo(obj, titulo):
    _boton_de_titulo(_caja(obj), titulo).click()
    _bombear()


def _subcaja(obj, titulo):
    return {"FACTOR SOBRE EL EJE": obj.subtool3, "LECTURAS DE LINEALIDAD": obj.subtool5}[titulo]


def _indice(subcaja, texto):
    return [subcaja.itemText(i) for i in range(subcaja.count())].index(texto)


def _elegir_en_el_menu(obj, titulo, grupo, hoja):
    """Lo que hace el físico: clic en el título y elegir en el menú (y en el submenú del grupo)."""
    _clic_en_titulo(obj, titulo)
    menu = _seccion(obj, titulo).menu
    assert menu is not None and menu.isVisible(), "el clic en el título no abrió el menú"
    acciones = {a.text(): a for a in menu.actions()}
    if grupo is not None:
        if grupo not in acciones or acciones[grupo].menu() is None:
            pytest.fail(f"el menú no tiene el grupo «{grupo}» con su submenú")
        acciones = {a.text(): a for a in acciones[grupo].menu().actions()}
    acciones[hoja].trigger()
    _bombear()
    return menu


def _color(accion_o_icono):
    icono = accion_o_icono.icon() if hasattr(accion_o_icono, "icon") else accion_o_icono
    c = icono.pixmap(14, 14).toImage().pixelColor(7, 7)
    return (c.red(), c.green(), c.blue())


def _accion(obj, titulo, grupo, hoja):
    menu = _seccion(obj, titulo).construir_menu()
    acciones = {a.text(): a for a in menu.actions()}
    if grupo is not None:
        acciones = {a.text(): a for a in acciones[grupo].menu().actions()}
    return acciones[hoja]


def _entrada(obj, lista, id_energia):
    return next(e for e in getattr(obj, lista) if e["id_energia"] == id_energia)


def _poner(tabla, fila, columna, texto):
    tabla.setItem(fila, columna, QTableWidgetItem(texto))


def _subir(tabla):
    """Pulsa el «Subir» de la página de la tabla (el de la última de PDD en el eje)."""
    pagina = tabla.parentWidget()
    while pagina is not None and not [b for b in pagina.findChildren(QPushButton) if b.text() == "Subir"]:
        pagina = pagina.parentWidget()
    botones = [b for b in pagina.findChildren(QPushButton) if b.text() == "Subir"]
    botones[-1].click()
    _bombear()


def _editor_abierto(tabla):
    editores = [w for w in tabla.findChildren(QLineEdit) if w.isVisible()]  # sin viewport(): su envoltorio sobrevive (Trampa 9)
    assert len(editores) == 1, "no se abrió el editor de la celda"
    return editores[0]


def _abrir_editor(tabla, fila, columna):
    if tabla.item(fila, columna) is None:
        tabla.setItem(fila, columna, QTableWidgetItem(""))
    tabla.setCurrentCell(fila, columna)
    tabla.editItem(tabla.item(fila, columna))
    _bombear()
    return _editor_abierto(tabla)


def _escribir_como_el_fisico(tabla, fila, columna, texto):
    """Lo que hace el físico: abrir el editor de la celda, teclear y pulsar Enter."""
    editor = _abrir_editor(tabla, fila, columna)
    editor.selectAll()
    QTest.keyClicks(editor, texto)
    QTest.keyClick(editor, Qt.Key_Return)
    _bombear()
    assert tabla.item(fila, columna).text() == texto


def _texto(tabla, fila, columna):
    item = tabla.item(fila, columna)
    return item.text() if item is not None else ""


def _llenar_linealidad(tabla):
    for fila in range(tabla.rowCount()):
        _poner(tabla, fila, 1, f"{1.0 + fila:.2f}")
        _poner(tabla, fila, 2, f"{1.0 + fila:.2f}")


def _llenar_eje(obj, id_energia):
    tablas = [e["tabla"] for e in obj.tablas_fse[id_energia]]
    for k, tabla in enumerate(tablas):
        for fila in range(tabla.rowCount()):
            _poner(tabla, fila, 1, f"{90 - 10 * fila - k:.1f}")
            _poner(tabla, fila, 2, f"{90 - 10 * fila - k:.1f}")
    return tablas


def _tablas_de(obj, lista, id_energia):
    if lista == "tablas_fse":
        return [e["tabla"] for e in obj.tablas_fse[id_energia]]
    return [_entrada(obj, lista, id_energia)["tabla"]]


def _recalcular(obj, calculo, tablas):
    """El recálculo que la app conecta a cada tabla (a los 300 [ms] de un cambio)."""
    for tabla in tablas:
        argumentos = (tabla, 1, 2) if calculo == "_calcular_discrepancias_tablas" else (tabla,)
        getattr(obj, calculo)(*argumentos)()


def _margenes(pagina):
    capas = [pagina.layout()] + pagina.findChildren(QLayout)
    return [(m.left(), m.top(), m.right(), m.bottom()) for m in (c.contentsMargins() for c in capas if c is not None)]


# --------------------------------------------------------------------------- el espacio

class TestElEspacio:
    @pytest.mark.parametrize("grupo,hoja", [("Lecturas de factor de campo", "15 MV"),
                                            ("Lecturas de transmisión de cuñas", "15 MV"),
                                            ("Linealidad de unidades monitor", "6 MeV")])
    def test_en_1920x980_la_tabla_elegida_mide_al_menos_500_px(self, paginas, grupo, hoja):
        obj = paginas()
        sub = obj.subtool5
        i = _indice(sub, f"{grupo} - {hoja}")
        if getattr(obj, "menu_linealidad", None) is not None:
            _elegir_en_el_menu(obj, "LECTURAS DE LINEALIDAD", grupo, hoja)
        else:
            caja = _caja(obj)
            caja.setCurrentIndex(_titulos(caja).index("LECTURAS DE LINEALIDAD"))
            sub.setCurrentIndex(i)
            _bombear()
        alto = sub.widget(i).height()
        assert alto >= 500, f"la tabla elegida queda con {alto} [px] de alto (pide al menos 500)"
        tabla = sub.widget(i).findChildren(QTableWidget)[0]
        assert tabla.height() >= 450, f"la tabla misma mide {tabla.height()} [px]"

    def test_factor_sobre_el_eje_muestra_sus_tres_pdd_con_mas_alto_que_hoy(self, paginas):
        obj = paginas()
        _elegir_en_el_menu(obj, "FACTOR SOBRE EL EJE", None, "15 MV")
        pagina = obj.subtool3.widget(1)
        tablas = pagina.findChildren(QTableWidget)
        assert len(tablas) == 3 and all(t.isVisible() for t in tablas)
        assert [t.horizontalHeaderItem(1).text() for t in tablas] == ["PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"]
        assert pagina.height() >= 500 and min(t.height() for t in tablas) >= 120
        barras = [b for t in tablas for b in t.findChildren(QScrollBar) if b.orientation() == Qt.Vertical]
        assert len(barras) >= 3 and all(b.maximum() == 0 for b in barras), "alguna tabla de PDD no muestra sus tres filas"


# --------------------------------------------------------------------------- el menú

class TestElMenu:
    def test_el_menu_de_linealidad_tiene_los_cinco_grupos_con_flechita_y_sus_energias(self, paginas):
        obj = paginas()
        menu = _seccion(obj, "LECTURAS DE LINEALIDAD").construir_menu()
        grupos = {a.text(): a.menu() for a in menu.actions()}
        assert list(grupos) == list(GRUPOS)
        assert all(sub is not None for sub in grupos.values()), "cada grupo debe abrir su submenú (flechita)"
        assert {g: [a.text() for a in sub.actions()] for g, sub in grupos.items()} == GRUPOS
        assert all(a.menu() is None and not a.icon().isNull() for sub in grupos.values() for a in sub.actions())
        assert all(a.icon().isNull() for a in menu.actions()), "un grupo no lleva circulito"
        # Lo que crea Qt deja un envoltorio muerto en Python si antes murió otra QApplication: violación de segmento
        propios = list(grupos.values()) + [a for sub in grupos.values() for a in sub.actions()]
        propios += [v for v in vars(_seccion(obj, "LECTURAS DE LINEALIDAD")).values() if isinstance(v, QObject)]
        assert all(sip.ispycreated(x) for x in propios), "submenús, acciones y lo que guarda la sección se crean desde Python"

    def test_los_dos_titulos_con_menu_llevan_su_flechita_abierta_o_cerrada(self, paginas):
        obj = paginas()
        caja = _caja(obj)

        def flechitas():
            return {t: None if caja.itemIcon(i).isNull() else _color(caja.itemIcon(i)) for i, t in enumerate(_titulos(caja))}
        esperado = {t: (FLECHITA if t in CON_MENU else None) for t in SECCIONES}
        assert flechitas() == esperado, "solo los dos títulos con menú llevan la flechita"
        _elegir_en_el_menu(obj, "LECTURAS DE LINEALIDAD", "Tasa de dosis (constancia)", "6 MV")
        assert flechitas() == esperado, "con la sección abierta"
        caja.setCurrentIndex(_titulos(caja).index("FACTOR DE CAMPO"))
        _bombear()
        assert flechitas() == esperado, "con la sección cerrada"
        assert _titulos(caja) == SECCIONES, "el texto de los títulos no cambia"

    def test_el_menu_del_eje_tiene_las_seis_energias_con_su_circulito(self, paginas):
        obj = paginas()
        menu = _seccion(obj, "FACTOR SOBRE EL EJE").construir_menu()
        assert [a.text() for a in menu.actions()] == ENERGIAS
        assert all(a.menu() is None and not a.icon().isNull() for a in menu.actions())

    def test_el_menu_es_gris_con_texto_simple(self, paginas):
        obj = paginas()
        menu = _seccion(obj, "LECTURAS DE LINEALIDAD").construir_menu()
        assert "#ececec" in menu.styleSheet() and "color:black" in menu.styleSheet()

    def test_al_construir_no_se_abre_ningun_menu(self, paginas):
        obj = paginas()
        assert QApplication.activePopupWidget() is None
        assert all(not m.isVisible() for m in obj.findChildren(QMenu))

    def test_el_clic_en_el_titulo_abre_el_menu_con_popup(self, paginas, monkeypatch):
        obj = paginas()
        pedidas, popup = [], QMenu.popup
        monkeypatch.setattr(QMenu, "popup", lambda menu, punto, *a: (pedidas.append(punto), popup(menu, punto, *a)))
        _clic_en_titulo(obj, "LECTURAS DE LINEALIDAD")
        menu = _seccion(obj, "LECTURAS DE LINEALIDAD").menu
        assert menu is not None and menu.isVisible()
        boton = _boton_de_titulo(_caja(obj), "LECTURAS DE LINEALIDAD")
        assert pedidas and pedidas[-1] == boton.mapToGlobal(QPoint(0, boton.height())), "el menú se abre debajo del título"

    def test_al_elegir_el_menu_se_cierra_y_solo_se_ve_esa_tabla(self, paginas):
        obj = paginas()
        menu = _elegir_en_el_menu(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "15 MV")
        assert not menu.isVisible() and all(not m.isVisible() for m in menu.findChildren(QMenu))
        sub = obj.subtool5
        i = _indice(sub, "Lecturas de factor de campo - 15 MV")
        assert sub.isVisible() and sub.currentIndex() == i and sub.widget(i).isVisible()
        assert [k for k in range(sub.count()) if sub.widget(k).isVisible()] == [i]
        botones = sub.findChildren(QAbstractButton, "qt_toolbox_toolboxbutton", Qt.FindDirectChildrenOnly)
        assert botones and not any(b.isVisible() for b in botones), "la cascada de subsecciones sigue a la vista"

    def test_la_barra_dice_la_tabla_actual_y_vuelve_a_abrir_el_menu(self, paginas):
        obj = paginas()
        seccion = _seccion(obj, "LECTURAS DE LINEALIDAD")
        _elegir_en_el_menu(obj, "LECTURAS DE LINEALIDAD", "Tasa de dosis (constancia)", "6 MV")
        assert seccion.barra.text().startswith("Tasa de dosis (constancia) - 6 MV") and "cambiar tabla" in seccion.barra.text()
        seccion.barra.click()
        _bombear()
        assert seccion.menu.isVisible()

    def test_sin_tabla_elegida_la_seccion_no_muestra_ninguna(self, paginas):
        obj = paginas()
        caja = _caja(obj)
        caja.setCurrentIndex(_titulos(caja).index("LECTURAS DE LINEALIDAD"))
        _bombear()
        seccion = _seccion(obj, "LECTURAS DE LINEALIDAD")
        assert not obj.subtool5.isVisible() and seccion.barra.isVisible()
        assert seccion.barra.text().startswith("Ninguna tabla elegida")

    def test_un_clic_en_el_titulo_ya_elegido_vuelve_a_abrir_el_menu(self, paginas):
        obj = paginas()
        _elegir_en_el_menu(obj, "FACTOR SOBRE EL EJE", None, "6 MV")
        _clic_en_titulo(obj, "FACTOR SOBRE EL EJE")
        assert _seccion(obj, "FACTOR SOBRE EL EJE").menu.isVisible()

    def test_cerrar_el_menu_sin_elegir_y_volver_a_clicar_lo_abre(self, paginas):
        obj = paginas()
        _clic_en_titulo(obj, "LECTURAS DE LINEALIDAD")
        seccion = _seccion(obj, "LECTURAS DE LINEALIDAD")
        seccion.menu.hide()
        _bombear()
        assert seccion.elegido is None and not obj.subtool5.isVisible()
        _clic_en_titulo(obj, "LECTURAS DE LINEALIDAD")
        assert seccion.menu.isVisible()

    def test_las_otras_cuatro_secciones_siguen_en_cascada(self, paginas):
        obj = paginas()
        caja = _caja(obj)
        assert _titulos(caja) == SECCIONES
        for titulo, sub, n in (("FACTOR DE CAMPO", obj.subtool, 6), ("FACTOR DE TRANSMISIÓN", obj.subtool2, 2),
                               ("CONTROL DE CÁMARAS", obj.subtool4, 6)):
            caja.setCurrentIndex(_titulos(caja).index(titulo))
            _bombear()
            assert caja.widget(_titulos(caja).index(titulo)) is sub and sub.count() == n
            botones = sub.findChildren(QAbstractButton, "qt_toolbox_toolboxbutton", Qt.FindDirectChildrenOnly)
            assert len(botones) == n and all(b.isVisible() for b in botones)
            _boton_de_titulo(caja, titulo).click()
            _bombear()
            assert QApplication.activePopupWidget() is None, f"{titulo} no debe abrir un menú"


# --------------------------------------------------------------------------- el respaldo

class TestSiElMenuNoSePuedeArmar:
    @pytest.mark.parametrize("falla", ["flechita", "boton"])
    def test_si_el_menu_no_se_puede_armar_la_seccion_queda_en_cascada_como_antes(self, paginas, monkeypatch, bd_temporal,
                                                                                falla):
        """AF3-D8: el fallo llega con la sección ya dentro de su contenedor; se deshace todo."""
        from ui.paginasControles.PruebasAnuales import menu_de_secciones as menu_mod

        def en_cascada(self, caja, subcaja, titulo, agrupar):
            caja.addItem(subcaja, titulo)
        with monkeypatch.context() as sin_menu:
            sin_menu.setattr(PruebaAnualIX, "_agregar_seccion_con_menu", en_cascada)
            como_antes = paginas()

        def fallar(*a, **k):
            raise RuntimeError("fallo sembrado al armar el menú")
        if falla == "flechita":
            monkeypatch.setattr(menu_mod, "flechita", fallar)
        else:
            monkeypatch.setattr(menu_mod.SeccionConMenu, "boton", property(fallar))
        obj = paginas()
        caja = _caja(obj)
        assert _titulos(caja) == SECCIONES, "ninguna sección sale dos veces"
        assert obj.menu_fse is None and obj.menu_linealidad is None
        for titulo in CON_MENU:
            sub, antes = _subcaja(obj, titulo), _subcaja(como_antes, titulo)
            i = SECCIONES.index(titulo)
            assert caja.widget(i) is sub and caja.itemIcon(i).isNull()
            _boton_de_titulo(caja, titulo).click()
            _bombear()
            assert caja.currentIndex() == i and sub.isVisible() and QApplication.activePopupWidget() is None
            botones = sub.findChildren(QAbstractButton, "qt_toolbox_toolboxbutton", Qt.FindDirectChildrenOnly)
            assert len(botones) == sub.count() and all(b.isVisible() for b in botones), "la cascada quedó sin sus títulos"
            assert [_margenes(sub.widget(k)) for k in range(sub.count())] == \
                [_margenes(antes.widget(k)) for k in range(antes.count())], "las páginas no quedaron como antes"
        tabla = _entrada(obj, "tablas_tasa_dosis", 0)["tabla"]
        obj.subtool5.setCurrentIndex(_indice(obj.subtool5, "Tasa de dosis (constancia) - 6 MV"))
        _bombear()
        assert tabla.isVisible()
        _llenar_linealidad(tabla)
        _subir(tabla)
        assert bd_temporal.execute("SELECT COUNT(*) FROM anual_tasa_dosis WHERE ref = ? AND (activo IS NULL OR activo = 1)",
                                   (obj.ref,)).fetchone()[0] == 4


# --------------------------------------------------------------------------- los circulitos

class TestLosCirculitos:
    def test_sin_nada_guardado_todo_esta_en_rojo(self, paginas):
        obj = paginas()
        for titulo in ("LECTURAS DE LINEALIDAD", "FACTOR SOBRE EL EJE"):
            seccion = _seccion(obj, titulo)
            assert {seccion.estado(i) for i in range(len(seccion.elementos))} == {"rojo"}
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "15 MV")) == ROJO

    def test_un_subir_que_sale_bien_lo_pone_verde_y_editar_lo_vuelve_rojo(self, paginas):
        obj = paginas()
        tabla = _entrada(obj, "tablas_lecturas_fc", 1)["tabla"]
        _llenar_linealidad(tabla)
        _subir(tabla)
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "15 MV")) == VERDE
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "6 MV")) == ROJO
        _poner(tabla, 0, 1, "9.99")
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "15 MV")) == ROJO
        _poner(tabla, 0, 1, "1.00")
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "15 MV")) == VERDE, "lo guardado"
        _poner(tabla, 0, 2, "")
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "15 MV")) == ROJO, "borrar edita"

    def test_con_datos_de_la_base_al_abrir_esta_en_verde(self, paginas):
        obj = paginas()
        tabla = _entrada(obj, "tablas_tasa_dosis", 0)["tabla"]
        _llenar_linealidad(tabla)
        _subir(tabla)
        otra = paginas()
        assert otra.ref == obj.ref, "la segunda página debe abrir el mismo control"
        assert _color(_accion(otra, "LECTURAS DE LINEALIDAD", "Tasa de dosis (constancia)", "6 MV")) == VERDE
        assert _color(_accion(otra, "LECTURAS DE LINEALIDAD", "Tasa de dosis (constancia)", "15 MV")) == ROJO

    def test_los_calculos_de_la_app_no_lo_vuelven_rojo(self, paginas):
        obj = paginas()
        tabla = _entrada(obj, "tablas_lecturas_transmision", 1)["tabla"]
        for fila, q in enumerate(["2.15", "1.75", "1.4675", "1.1225", "0.9275", "0.4"]):
            _poner(tabla, fila, 1, q)
            _poner(tabla, fila, 2, q)
        _subir(tabla)
        assert _seccion(obj, "LECTURAS DE LINEALIDAD").estado(_indice(obj.subtool5, "Lecturas de transmisión de cuñas - 15 MV")) == "verde"
        for fila in range(tabla.rowCount()):
            _poner(tabla, fila, 5, "")
            _poner(tabla, fila, 6, "")
        obj._derivar_factor_transmision(tabla)()
        assert tabla.item(2, 5).text() != ""
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Lecturas de transmisión de cuñas", "15 MV")) == VERDE

    @pytest.mark.parametrize("titulo,grupo,hoja,columna", [
        ("LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "15 MV", 4),
        ("FACTOR SOBRE EL EJE", None, "6 MV", 3)])
    def test_corregir_a_mano_una_celda_calculada_lo_vuelve_rojo(self, sin_recalculo_diferido, paginas, titulo, grupo, hoja,
                                                                 columna):
        obj = paginas()
        if grupo is None:
            _llenar_eje(obj, 0)
            tabla = obj.tablas_fse[0][1]["tabla"]
            _subir(obj.tablas_fse[0][-1]["tabla"])
        else:
            tabla = _entrada(obj, "tablas_lecturas_fc", 1)["tabla"]
            _llenar_linealidad(tabla)
            _subir(tabla)
        assert _color(_accion(obj, titulo, grupo, hoja)) == VERDE
        _elegir_en_el_menu(obj, titulo, grupo, hoja)
        _escribir_como_el_fisico(tabla, 0, columna, "0.5")
        assert _color(_accion(obj, titulo, grupo, hoja)) == ROJO
        assert _color(_seccion(obj, titulo).barra.icon()) == ROJO

    def test_volver_a_escribir_lo_guardado_lo_devuelve_a_verde(self, sin_recalculo_diferido, paginas):
        obj = paginas()
        tabla = _entrada(obj, "tablas_lecturas_fc", 0)["tabla"]
        _llenar_linealidad(tabla)
        obj._derivar_factor_lecturas_campo(tabla)()
        _subir(tabla)
        _elegir_en_el_menu(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "6 MV")
        guardado = tabla.item(1, 4).text()
        assert guardado != "0.5"
        _escribir_como_el_fisico(tabla, 1, 4, "0.5")
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "6 MV")) == ROJO
        _escribir_como_el_fisico(tabla, 1, 4, guardado)
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "6 MV")) == VERDE

    def test_un_subir_que_falla_deja_el_rojo(self, paginas, monkeypatch):
        obj = paginas()
        tabla = _entrada(obj, "tablas_linealidad_um", 2)["tabla"]
        _llenar_linealidad(tabla)
        monkeypatch.setattr(ix_anual_mod, "loadtablacomplex", lambda *a, **k: False)
        _subir(tabla)
        assert _color(_accion(obj, "LECTURAS DE LINEALIDAD", "Linealidad de unidades monitor", "6 MeV")) == ROJO

    def test_el_eje_es_verde_solo_si_sus_tres_pdd_vienen_de_la_base(self, paginas, bd_temporal):
        obj = paginas()
        for id_energia in (0, 1):
            _llenar_eje(obj, id_energia)
            _subir(obj.tablas_fse[id_energia][-1]["tabla"])
        assert _color(_accion(obj, "FACTOR SOBRE EL EJE", None, "15 MV")) == VERDE
        for id_energia, pdd in ((1, "PPD (20 x 20)"), (0, "PDD (10 x 10)")):
            bd_temporal.execute("UPDATE tabla_factores_sobre_eje SET activo = 0 WHERE ref = ? AND id_energia = ? AND tam_pdd = ?",
                                (obj.ref, id_energia, pdd))
        bd_temporal.commit()
        otra = paginas()
        assert _color(_accion(otra, "FACTOR SOBRE EL EJE", None, "15 MV")) == ROJO, "falta su último PDD"
        assert _color(_accion(otra, "FACTOR SOBRE EL EJE", None, "6 MV")) == ROJO, "falta su primer PDD"

    def test_el_subir_del_eje_guarda_sus_tres_pdd_y_las_pone_en_verde(self, paginas, bd_temporal):
        obj = paginas()
        _llenar_eje(obj, 0)
        _subir(obj.tablas_fse[0][-1]["tabla"])
        filas = bd_temporal.execute("SELECT tam_pdd, COUNT(*) FROM tabla_factores_sobre_eje WHERE ref = ? AND id_energia = 0 "
                                    "AND (activo IS NULL OR activo = 1) GROUP BY tam_pdd ORDER BY tam_pdd", (obj.ref,)).fetchall()
        assert filas == [("PDD (10 x 10)", 3), ("PPD (15 x 15)", 3), ("PPD (20 x 20)", 3)]
        otra = paginas()
        assert _color(_accion(otra, "FACTOR SOBRE EL EJE", None, "6 MV")) == VERDE
        obj.tablas_fse[0][0]["tabla"].setItem(1, 1, QTableWidgetItem("11.1"))
        assert _color(_accion(obj, "FACTOR SOBRE EL EJE", None, "6 MV")) == ROJO

    def test_la_barra_lleva_el_circulito_de_la_tabla_elegida(self, paginas):
        obj = paginas()
        tabla = _entrada(obj, "tablas_lecturas_fc", 0)["tabla"]
        _elegir_en_el_menu(obj, "LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "6 MV")
        barra = _seccion(obj, "LECTURAS DE LINEALIDAD").barra
        assert _color(barra.icon()) == ROJO and barra.toolTip() == "Sin guardar"
        _llenar_linealidad(tabla)
        _subir(tabla)
        assert _color(barra.icon()) == VERDE and barra.toolTip() == "Guardada"
        menu = _seccion(obj, "LECTURAS DE LINEALIDAD").construir_menu()
        grupo = {a.text(): a for a in menu.actions()}["Lecturas de factor de campo"].menu()
        assert menu.toolTipsVisible() and grupo.toolTipsVisible(), "los avisos del menú y de sus grupos se ven"
        assert {a.text(): a.toolTip() for a in grupo.actions()} == {"6 MV": "Guardada", "15 MV": "Sin guardar"}
        _poner(tabla, 0, 2, "7.77")
        assert _color(barra.icon()) == ROJO and barra.toolTip() == "Sin guardar"
        tres = _llenar_eje(obj, 0)
        _subir(tres[-1])
        _elegir_en_el_menu(obj, "FACTOR SOBRE EL EJE", None, "6 MV")
        barra_del_eje = _seccion(obj, "FACTOR SOBRE EL EJE").barra
        assert _color(barra_del_eje.icon()) == VERDE
        _poner(tres[2], 1, 1, "11.1")
        assert _color(barra_del_eje.icon()) == ROJO, "editar el tercer PDD también mueve la barra"

    @pytest.mark.parametrize("titulo,grupo,hoja,lista,id_energia,calculo,columnas", [
        ("LECTURAS DE LINEALIDAD", "Linealidad de unidades monitor", "6 MV", "tablas_linealidad_um", 0,
         "_derivar_factor_linealidad_um", (3,)),
        ("LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "6 MV", "tablas_lecturas_fc", 0,
         "_derivar_factor_lecturas_campo", (3, 4)),
        ("LECTURAS DE LINEALIDAD", "Lecturas de factor de cono", "6 MeV", "tablas_lecturas_fc", 2,
         "_derivar_factor_lecturas_campo", (3, 4)),
        ("LECTURAS DE LINEALIDAD", "Lecturas de transmisión de cuñas", "6 MV", "tablas_lecturas_transmision", 0,
         "_derivar_factor_transmision", (5, 6)),
        ("FACTOR SOBRE EL EJE", None, "6 MV", "tablas_fse", 0, "_calcular_discrepancias_tablas", (3,))])
    def test_el_recalculo_de_la_app_tras_cargar_un_control_guardado_sigue_verde(self, paginas, titulo, grupo, hoja, lista,
                                                                                 id_energia, calculo, columnas):
        """Cada columna que calcula la app: al recalcular lo cargado la reescribe con otro formato y sigue verde."""
        obj = paginas()
        tablas = _tablas_de(obj, lista, id_energia)
        if lista == "tablas_fse":
            _llenar_eje(obj, id_energia)
        else:
            _llenar_linealidad(tablas[0])
        _recalcular(obj, calculo, tablas)
        _subir(tablas[-1])
        otra = paginas()
        cargadas = _tablas_de(otra, lista, id_energia)
        assert _color(_accion(otra, titulo, grupo, hoja)) == VERDE

        def columna(c):
            return [_texto(t, f, c) for t in cargadas for f in range(t.rowCount())]
        antes = {c: columna(c) for c in columnas}
        _recalcular(otra, calculo, cargadas)
        assert [c for c in columnas if columna(c) == antes[c]] == [], "el recálculo no reescribió estas columnas"
        assert _color(_accion(otra, titulo, grupo, hoja)) == VERDE

    @pytest.mark.parametrize("gesto", ["enter", "tab", "reteclear"])
    def test_confirmar_el_editor_sin_cambiar_nada_no_cuenta_como_correccion(self, sin_recalculo_diferido, paginas, gesto):
        """Mirar una celda calculada y salir sin cambiarla no la anota: el recálculo posterior no la vuelve roja."""
        obj = paginas()
        tabla = _entrada(obj, "tablas_lecturas_fc", 0)["tabla"]
        _llenar_linealidad(tabla)
        obj._derivar_factor_lecturas_campo(tabla)()
        _subir(tabla)
        otra = paginas()
        cargada = _entrada(otra, "tablas_lecturas_fc", 0)["tabla"]
        clave = ("LECTURAS DE LINEALIDAD", "Lecturas de factor de campo", "6 MV")
        _elegir_en_el_menu(otra, *clave)
        antes = {c: _texto(cargada, 0, c) for c in (3, 4)}
        if gesto == "tab":
            QTest.keyClick(_abrir_editor(cargada, 0, 3), Qt.Key_Tab)  # confirma y abre el editor de la celda de al lado
            _bombear()
            assert cargada.currentColumn() == 4
            QTest.keyClick(_editor_abierto(cargada), Qt.Key_Tab)
            _bombear()
        else:
            for c in (3, 4):
                if gesto == "enter":
                    QTest.keyClick(_abrir_editor(cargada, 0, c), Qt.Key_Return)
                    _bombear()
                else:
                    _escribir_como_el_fisico(cargada, 0, c, antes[c])
        assert _color(_accion(otra, *clave)) == VERDE, "mirar no edita"
        otra._derivar_factor_lecturas_campo(cargada)()
        assert all(_texto(cargada, 0, c) != antes[c] for c in (3, 4)), "el recálculo no reescribió las celdas miradas"
        assert _color(_accion(otra, *clave)) == VERDE, "solo cuenta lo que el físico cambió"


# --------------------------------------------------------------------------- P3 y E1

class TestSinCunasDeElectrones:
    def test_factor_de_transmision_solo_tiene_fotones(self, paginas):
        obj = paginas()
        assert [e["id_energia"] for e in obj.tablas_fta] == [0, 1]
        assert [obj.subtool2.itemText(i) for i in range(obj.subtool2.count())] == [
            "Medida de factor de transmisión de accesorios - 6 MV", "Medida de factor de transmisión de accesorios - 15 MV"]

    def test_lecturas_de_transmision_solo_tiene_fotones(self, paginas):
        obj = paginas()
        assert [e["id_energia"] for e in obj.tablas_lecturas_transmision] == [0, 1]
        assert not [t for t in (obj.subtool5.itemText(i) for i in range(obj.subtool5.count())) if "cuñas" in t and "MeV" in t]
        assert obj.subtool5.count() == 16


class TestE1LaCunaDe15MVContraSuAbierto:
    def test_la_cuna_de_30_de_15_mv_da_0683_y_no_0802(self, paginas):
        """H9/E1: con las lecturas del iX de 2026, cada cuña se divide por el abierto de SU energía (15 MV: 2.15)."""
        obj = paginas()
        tabla = _entrada(obj, "tablas_lecturas_transmision", 1)["tabla"]
        lecturas = {"Open": ["2.15", "2.15"], "15°": ["1.75", "1.75", "1.75", "1.75"], "30°": ["1.46", "1.47", "1.47", "1.47"],
                    "45°": ["1.12", "1.12", "1.13", "1.12"], "60°": ["0.92", "0.93", "0.93", "0.93"], "MLC": ["0.4", "0.4"]}
        for fila in range(tabla.rowCount()):
            for k, q in enumerate(lecturas[tabla.item(fila, 0).text()]):
                _poner(tabla, fila, 1 + k, q)
        obj._derivar_factor_transmision(tabla)()
        t = {tabla.item(f, 0).text(): float(tabla.item(f, 6).text()) for f in range(tabla.rowCount())}
        assert round(t["30°"], 3) == 0.683 and round(t["45°"], 3) == 0.522 and round(t["60°"], 3) == 0.431
        assert round(t["30°"], 3) != 0.802
        assert round(t["MLC"], 3) == 0.186


# --------------------------------------------------------------------------- lo que se guarda no cambia

class TestLoGuardadoNoCambia:
    def test_la_tasa_de_dosis_sube_las_mismas_filas_de_siempre(self, paginas, bd_temporal):
        obj = paginas()
        tabla = _entrada(obj, "tablas_tasa_dosis", 1)["tabla"]
        _llenar_linealidad(tabla)
        _subir(tabla)
        filas = bd_temporal.execute("SELECT id_energia, tasa_um_min, med1, med2 FROM anual_tasa_dosis WHERE ref = ? "
                                    "AND (activo IS NULL OR activo = 1) ORDER BY id", (obj.ref,)).fetchall()
        assert filas == [(1, "100", 1.0, 1.0), (1, "300", 2.0, 2.0), (1, "400", 3.0, 3.0), (1, "600", 4.0, 4.0)]

    def test_build_exe_lleva_el_modulo_nuevo_una_vez_y_sigue_en_crlf(self):
        with open(os.path.join(RAIZ, "build_exe.py"), "rb") as f:
            texto = f.read()
        assert texto.count(b'"ui.paginasControles.PruebasAnuales.menu_de_secciones",') == 1
        assert texto.count(b"\r\n") == texto.count(b"\n")
