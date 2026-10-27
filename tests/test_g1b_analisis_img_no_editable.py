"""G.1b (27-10-2026; PLAN_ANALISIS_PELICULAS_08-10.md, DA-91): la celda «Analisis Img» de la tabla de controles del mensual lleva un item vacio y NO editable.

G.1 (3ca6133) dejo esa celda sin boton y sin item (columna 15 del 600 y del iX, columna 9 del Halcyon). Sin item, `verificar_editar` (que solo avisa cuando HAY un item sin metadatos) pide la contrasena y despues
`editar_tablas` dice «Celda vacia o no editable», y el doble clic abre el cuadro de texto, cuyo contenido queda en pantalla sin guardarse. El fisico eligio la opcion (a) de G1-D1 (26-10: «G1-D1 me quedo con la
opcion a.»): un item vacio y no editable, como cualquier celda sin tabla de origen de esa funcion. Lo que se fija, en los tres equipos, sobre una base sembrada (tres controles, con y sin `preguntas`) y sobre la
copia de la produccion del 06-10, en TODAS las filas:

  1. EL ITEM: la columna «Analisis Img» (con su encabezado, en la 15 del 600 y del iX y en la 9 del Halcyon) lleva un item de texto vacio, sin `Qt.ItemIsEditable`, con las mismas banderas que las demas celdas
     sin tabla de origen (la celda «Imagen» de la misma fila: tambien seleccionable, el clic la elige), sin metadatos (`Qt.UserRole + 1`) y sin widget. La definicion del predicado es la de
     `test_g1_analisis_viejo_retirado._problemas_del_item_vacio` (una sola); aqui tiene su caso sintetico por defecto.
  2. «EDITAR»: con la celda elegida (`currentRow` y `currentColumn` puestos ahi), `verificar_editar` avisa «Edicion no permitida» / «Este campo no se puede editar.» y NO abre `DialogAdminPermisoEditar`. Control: sobre
     una celda sin item (un boton de «Ver tabla») SI pide la contrasena y no avisa, y en el 600 y el iX sobre «Dif. Punt - Tel» (con metadatos) tambien: la prueba distingue las tres conductas.
  3. EL DOBLE CLIC: abrir el editor (`edit(indice)` y `editItem(item)`, con todos los disparadores) sobre la celda no deja la tabla en `EditingState`. Controles: sobre un item editable de la tabla (la «Fecha»)
     y, en una tabla sintetica, sobre una celda sin item NI widget (lo que era la celda de G.1) SI entra. Una celda con un boton de «Ver tabla» NO sirve de control del editor (medido en el 600, el iX y el Halcyon:
     Qt no abre el editor sobre un widget de celda, `edit: editing failed` y `NoState`); ese boton es el control de «Editar» (punto 2), que si pide la contrasena.
  4. LO DE AL LADO NO CAMBIA: «Dif. Punt - Tel» (600 e iX) sigue con su valor, editable y con sus metadatos; en el Halcyon la celda «Imagen» de al lado sigue ahi; las columnas son las de siempre.

Trampa 2 (todo cuadro se parcha: la fixture `dialogos` de `_e1_ayudas` para los `QMessageBox`, y `DialogAdminPermisoEditar` por un falso que anota que se abrio), Trampa 3 (`sys.excepthook` propio, el de G.1), Trampa 9
(la tabla se cierra por completo), Trampa 10 (ni `lru_cache` ni `skip` por parametro). Ninguna BD de referencia se abre directo: la copia de la produccion la hace la fixture de G.1.
Rojo contra HEAD (3ca6133): caen 1, 2 y 3 (no hay item: `tabla.item(f, c)` es None; «Editar» pide la contrasena; el editor se abre) y pasan los controles y lo de al lado.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem

from _e1_ayudas import _cursor_limpio, app, cerrar, dialogos  # noqa: F401  (fixtures y ayudas de E.1)
from test_g1_analisis_viejo_retirado import (  # noqa: F401  (las fixtures y ayudas de G.1: una sola definicion, corolario 1)
    ANALISIS_IMG, EQUIPOS, _cargar_la_tabla, _columnas, _consulta, _excepciones_de_slots, _problemas_del_item_vacio, _sql, _texto_de_la_celda, base_nueva, produccion)

FAMILIAS = ("600", "ix", "halcyon")
COLUMNA_ESPERADA = {"600": 15, "ix": 15, "halcyon": 9}                    # donde vive «Analisis Img» en cada equipo (el plan: 15 en el 600 y el iX, 9 en el Halcyon)
AVISO = ("Edición no permitida", "Este campo no se puede editar.")
COLUMNAS_DE_VALORES_600_IX = {10: "Cami. Rango", 11: "Cami. Desp", 12: "Des. Isocentro", 13: "Rango Tel.", 14: "Des. Tel", 16: "Dif. Punt - Tel", 17: "Lás. Techo", 18: "Lás. 90°", 19: "Lás. 270°"}   # las de `preguntas` a ambos lados de la 15
UN_BOTON = "Tam. Campos"                                                  # una columna de «Ver tabla»: no tiene item, asi que «Editar» sobre ella pide la contrasena (lo que pasaba con «Analisis Img» en G.1)


def _sembrar(base, familia):
    """Tres controles mensuales: dos con su fila de `preguntas` (uno con el valor de «Dif. Punt - Tel» en NULL) y uno sin ella. Devuelve los `ref`."""
    equipo = EQUIPOS[familia]
    refs = []
    for dia, puntero in (("15/03/2026", "0.25"), ("15/04/2026", None), ("15/05/2026", "0.40")):             # un control por mes y equipo (`idx_controles_unico_mes`)
        ref = _sql(base, "INSERT INTO controles (equipo, control, fecha, user_id, activo) VALUES (?, 'Mensual', ?, 'Fisico Uno', 1)", (equipo, dia))
        refs.append(ref)
        if familia != "halcyon" and dia != "15/05/2026":
            _sql(base, "INSERT INTO preguntas (ref, iso_mec, puntero_telem_diff, telem_rango, laser_techo, activo) VALUES (?, 1.0, ?, '3.5', '0.5', 1)", (ref, puntero))
    return refs


@pytest.fixture(params=[(origen, familia) for origen in ("sembrada", "produccion") for familia in FAMILIAS], ids=lambda p: f"{p[0]}-{p[1]}")
def caso(request, dialogos):
    """La tabla de controles del equipo, cargada con `mostrar_controles_mensuales` sobre una base sembrada o sobre la copia de la produccion del 06-10 (nunca la original)."""
    origen, familia = request.param
    base = request.getfixturevalue("base_nueva" if origen == "sembrada" else "produccion")
    if origen == "sembrada":
        _sembrar(base, familia)
    tabla = _cargar_la_tabla(EQUIPOS[familia])
    assert tabla.rowCount() > 0, "la prueba no puede ser vacua"
    yield SimpleNamespace(tabla=tabla, familia=familia, origen=origen, base=base, dialogos=dialogos, columna=_columnas(tabla)[ANALISIS_IMG])
    cerrar(tabla)


@pytest.fixture
def contrasena(monkeypatch):
    """Sustituye `DialogAdminPermisoEditar` (el cuadro modal que pide la contrasena, Trampa 2) por uno que anota que se abrio y se rechaza solo; devuelve la lista de aperturas."""
    import ui.paginasGuia.dialogs as dlgs
    abiertos = []

    class Falso:
        def __init__(self, *args, **kwargs):
            abiertos.append(args)

        def exec(self):
            return 0
    monkeypatch.setattr(dlgs, "DialogAdminPermisoEditar", Falso)
    return abiertos


def _editar(caso, contrasena, fila, columna):
    """Lo que hace el boton «Editar» con la celda `(fila, columna)` elegida: `verificar_editar`. Devuelve (avisos, veces que pidio la contrasena)."""
    import data.ManejoDatos.load as load
    caso.dialogos.llamadas.clear()
    contrasena.clear()
    caso.tabla.setCurrentCell(fila, columna)
    assert (caso.tabla.currentRow(), caso.tabla.currentColumn()) == (fila, columna)
    load.verificar_editar(SimpleNamespace(user_id=1), caso.tabla, "preguntas", "ref", caso.tabla.item(fila, 0).data(Qt.UserRole))
    return [(c["titulo"], c["texto"]) for c in caso.dialogos.de("warning")], len(contrasena)


# ====================================================================================================================================== 1. el item

class TestElItemDeLaCelda:
    def test_la_columna_y_su_encabezado_estan_donde_el_plan_dice(self, caso):
        assert _columnas(caso.tabla)[ANALISIS_IMG] == COLUMNA_ESPERADA[caso.familia]
        assert caso.tabla.horizontalHeaderItem(COLUMNA_ESPERADA[caso.familia]).text() == ANALISIS_IMG

    def test_cada_fila_lleva_un_item_vacio_no_editable_sin_metadatos_ni_widget(self, caso):
        problemas = {f: p for f in range(caso.tabla.rowCount()) if (p := _problemas_del_item_vacio(caso.tabla, f, caso.columna))}
        assert problemas == {}, problemas

    def test_la_celda_tiene_las_mismas_banderas_que_imagen_y_el_clic_la_elige_en_cada_fila(self, caso):
        """«Igual que las demas celdas sin tabla de origen de esa funcion» (el plan): la celda «Imagen» de la misma fila es la vecina real sin tabla de origen. Con `setFlags(Qt.ItemIsEnabled)` (el modismo habitual
        para «no editable») la celda queda con banderas 32 en lugar de 61, sin `Qt.ItemIsSelectable`: el clic ya no la elige y se ve distinta de su vecina aunque «Editar» siga avisando."""
        columnas = _columnas(caso.tabla)
        imagen = columnas["Imagen"]
        sin_item = [f for f in range(caso.tabla.rowCount()) if caso.tabla.item(f, caso.columna) is None or caso.tabla.item(f, imagen) is None]
        assert sin_item == [], f"falta el item de la celda o el de «Imagen» en las filas {sin_item}"
        distintas = {f: (int(caso.tabla.item(f, caso.columna).flags()), int(caso.tabla.item(f, imagen).flags())) for f in range(caso.tabla.rowCount())
                     if int(caso.tabla.item(f, caso.columna).flags()) != int(caso.tabla.item(f, imagen).flags())}
        assert distintas == {}, f"banderas de la celda y de «Imagen» por fila: {distintas}"
        sin_elegir = []
        for f in range(caso.tabla.rowCount()):
            caso.tabla.setCurrentCell(f, caso.columna)
            if not caso.tabla.selectionModel().isSelected(caso.tabla.model().index(f, caso.columna)):
                sin_elegir.append(f)
        assert sin_elegir == [], f"el clic no elige la celda en las filas {sin_elegir}"

    def test_el_detector_caza_cada_forma_de_dejar_mal_la_celda(self, app):
        """El predicado de G.1 con casos sinteticos: la celda correcta pasa, y cada defecto se caza por su cuenta (para que ninguna de las pruebas de arriba sea vacua)."""
        tabla = QTableWidget(6, 1)
        try:
            buena = QTableWidgetItem("")
            buena.setFlags(buena.flags() & ~Qt.ItemIsEditable)
            tabla.setItem(0, 0, buena)
            assert _problemas_del_item_vacio(tabla, 0, 0) == []
            assert len(_problemas_del_item_vacio(tabla, 1, 0)) == 1, "sin item"
            con_texto = QTableWidgetItem("-")
            con_texto.setFlags(con_texto.flags() & ~Qt.ItemIsEditable)
            tabla.setItem(2, 0, con_texto)
            assert len(_problemas_del_item_vacio(tabla, 2, 0)) == 1, "con texto"
            editable = QTableWidgetItem("")
            tabla.setItem(3, 0, editable)
            assert len(_problemas_del_item_vacio(tabla, 3, 0)) == 1, "editable"
            con_meta = QTableWidgetItem("")
            con_meta.setFlags(con_meta.flags() & ~Qt.ItemIsEditable)
            con_meta.setData(Qt.UserRole + 1, ("preguntas", "puntero_telem_diff"))
            tabla.setItem(4, 0, con_meta)
            assert len(_problemas_del_item_vacio(tabla, 4, 0)) == 1, "con metadatos"
            sin_seleccion = QTableWidgetItem("")
            sin_seleccion.setFlags(Qt.ItemIsEnabled)                          # no editable, pero tampoco seleccionable ni arrastrable: no es como las demas celdas sin tabla de origen
            tabla.setItem(5, 0, sin_seleccion)
            assert len(_problemas_del_item_vacio(tabla, 5, 0)) == 1, "con otras banderas"
        finally:
            cerrar(tabla)


# ====================================================================================================================================== 2. «Editar»

class TestEditarSobreLaCelda:
    def test_editar_avisa_que_el_campo_no_se_puede_editar_y_no_pide_la_contrasena_en_cada_fila(self, caso, contrasena):
        resultados = {f: _editar(caso, contrasena, f, caso.columna) for f in range(caso.tabla.rowCount())}
        assert resultados == {f: ([AVISO], 0) for f in range(caso.tabla.rowCount())}, resultados

    def test_control_una_celda_sin_item_si_pide_la_contrasena_y_no_avisa(self, caso, contrasena):
        """Lo que pasaba con «Analisis Img» en G.1 (sin item): la prueba distingue «avisa» de «pide la contrasena»."""
        c = _columnas(caso.tabla)[UN_BOTON]
        assert caso.tabla.item(0, c) is None and caso.tabla.cellWidget(0, c) is not None, "el control: un boton y ningun item"
        assert _editar(caso, contrasena, 0, c) == ([], 1)

    def test_control_dif_punt_tel_con_metadatos_si_pide_la_contrasena_y_no_avisa(self, caso, contrasena):
        if caso.familia == "halcyon":                                         # sin skip por parametro (Trampa 10): el Halcyon no tiene esa columna y su control es el del boton
            assert "Dif. Punt - Tel" not in _columnas(caso.tabla)
            return
        c = _columnas(caso.tabla)["Dif. Punt - Tel"]
        assert _editar(caso, contrasena, 0, c) == ([], 1)


# ====================================================================================================================================== 3. el doble clic

class TestElEditorNoSeAbreSobreLaCelda:
    """El doble clic llega a `QAbstractItemView.edit(indice)` con todos los disparadores: se llama igual, por el INDICE (y no por `editItem(item)`), para que la prueba valga tambien cuando la celda no tiene item
    (G.1: Qt trata una celda sin item como editable y el editor se abre)."""

    def test_abrir_el_editor_sobre_la_celda_no_deja_la_tabla_en_edicion_en_ninguna_fila(self, caso):
        caso.tabla.setEditTriggers(QAbstractItemView.AllEditTriggers)
        en_edicion = []
        for f in range(caso.tabla.rowCount()):
            caso.tabla.edit(caso.tabla.model().index(f, caso.columna))
            if caso.tabla.state() == QAbstractItemView.EditingState:
                en_edicion.append(f)
                break
        assert en_edicion == [], f"el editor se abrio sobre «{ANALISIS_IMG}» en la fila {en_edicion}"

    def test_abrir_el_editor_con_edititem_tampoco_lo_abre(self, caso):
        caso.tabla.setEditTriggers(QAbstractItemView.AllEditTriggers)
        for f in range(caso.tabla.rowCount()):
            item = caso.tabla.item(f, caso.columna)
            assert item is not None, f"la fila {f} no tiene item"
            caso.tabla.editItem(item)
            assert caso.tabla.state() != QAbstractItemView.EditingState, f

    def test_control_un_item_editable_de_la_misma_tabla_si_entra_en_edicion(self, caso):
        """Sin este control la prueba de arriba no probaria nada (una tabla que nunca edita, por estar oculta o sin disparadores, la pasaria): la «Fecha» (columna 0) es editable."""
        caso.tabla.setEditTriggers(QAbstractItemView.AllEditTriggers)
        item = caso.tabla.item(0, 0)
        assert item.flags() & Qt.ItemIsEditable
        caso.tabla.edit(caso.tabla.model().index(0, 0))
        assert caso.tabla.state() == QAbstractItemView.EditingState

    def test_control_una_celda_sin_item_ni_widget_se_abre_a_la_edicion_como_lo_hacia_la_celda_de_g1(self, app):
        """El comportamiento que DA-91 quita (la celda de G.1 no tenia item ni widget): en una tabla de Qt una celda asi se abre al editor. Si esto dejara de ser cierto, la prueba de arriba perderia su punto de
        comparacion. (Una celda con un boton, que es un widget de celda, no sirve de control: Qt no abre el editor sobre ella.)"""
        tabla = QTableWidget(2, 2)
        try:
            tabla.setEditTriggers(QAbstractItemView.AllEditTriggers)
            assert tabla.item(0, 1) is None and tabla.cellWidget(0, 1) is None
            tabla.edit(tabla.model().index(0, 1))
            assert tabla.state() == QAbstractItemView.EditingState
        finally:
            cerrar(tabla)


# ====================================================================================================================================== 4. lo de al lado

class TestLoDeAlLadoNoCambia:
    def test_dif_punt_tel_sigue_con_su_valor_editable_y_sus_metadatos_en_el_600_y_el_ix(self, caso):
        if caso.familia == "halcyon":
            assert "Dif. Punt - Tel" not in _columnas(caso.tabla), "el Halcyon nunca tuvo esa columna"
            return
        columnas = _columnas(caso.tabla)
        c = columnas["Dif. Punt - Tel"]
        assert c == caso.columna + 1, "la celda vacia no le quito su lugar"
        for f in range(caso.tabla.rowCount()):
            ref = caso.tabla.item(f, 0).data(Qt.UserRole)
            vigentes = _consulta(caso.base, "SELECT puntero_telem_diff FROM preguntas WHERE ref = ? AND (activo IS NULL OR activo = 1)", (ref,))
            esperado = _texto_de_la_celda(vigentes[0][0]) if vigentes else ""
            item = caso.tabla.item(f, c)
            assert item is not None and item.text() == esperado, (f, ref, esperado)
            assert item.flags() & Qt.ItemIsEditable, f
            assert item.data(Qt.UserRole + 1) == ("preguntas", "puntero_telem_diff"), f
            assert item.data(Qt.UserRole) == ref, f

    def test_las_columnas_de_valores_vecinas_conservan_sus_celdas_en_el_600_y_el_ix(self, caso):
        """Las nueve columnas de `preguntas` que rodean a «Analisis Img» (10-14 y 16-19, por su nombre y su lugar) tienen un item en cada fila, y «Analisis Img» (la 15) no es una de ellas. Se miran las nueve: un bucle
        que empiece o termine mal, en cualquiera de sus dos bordes, deja a la primera o a la ultima sin celda."""
        if caso.familia == "halcyon":
            return
        columnas = _columnas(caso.tabla)
        for columna, nombre in COLUMNAS_DE_VALORES_600_IX.items():
            assert columnas[nombre] == columna, (nombre, columnas[nombre], columna)
            sin_item = [f for f in range(caso.tabla.rowCount()) if caso.tabla.item(f, columna) is None]
            assert sin_item == [], f"«{nombre}» (columna {columna}) sin item en las filas {sin_item}"
        assert columnas[ANALISIS_IMG] == 15 and caso.tabla.columnCount() == 23

    def test_la_celda_imagen_de_al_lado_sigue_en_el_halcyon(self, caso):
        """La celda «Imagen» (columna 10) es la de siempre: un item de texto «Imagen Cargada» en cada fila (hoy lo dice en toda fila porque lee `cm.equipo` y no la imagen: es DP-162, de antes de G.1; si
        ese hallazgo se arregla, esta asercion se actualiza con el), no editable y sin metadatos (el encabezado de la 9 no los tiene). La celda vacia de la 9 no la pisa ni la deja sin item."""
        if caso.familia != "halcyon":
            assert caso.tabla.item(0, _columnas(caso.tabla)["Imagen"]) is not None
            return
        columnas = _columnas(caso.tabla)
        assert columnas["Imagen"] == caso.columna + 1
        for f in range(caso.tabla.rowCount()):
            item = caso.tabla.item(f, columnas["Imagen"])
            assert item is not None, f
            assert (item.text(), bool(item.flags() & Qt.ItemIsEditable), item.data(Qt.UserRole + 1)) == ("Imagen Cargada", False, None), f
        assert caso.tabla.columnCount() == 13
