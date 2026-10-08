"""GI.3 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, H1, H2, H6, D3 y D4) y cierre de las deudas que GI.2 dejo declaradas: lo que imprime el PDF de imagenes,
lo que dice «Ver tabla» de resolucion espacial, y que ninguna pantalla de lo guardado pueda dejar muda o vacia la reapertura.

CAUSA (medida el 07-10 sobre las copias de las BD de referencia): despues de GI.2 los lectores entregaban las claves del analisis, pero el PDF seguia leyendo
las de antes. La tabla de uniformidad leia `hu_promedio` (el analisis dice `promedio_hu`) y imprimia «N/A» en el HU de las cinco regiones; la de contraste leia
`rois_visibles_visibilidad_lim` y `pasa_test_visibilidad_lim` (NULL y 0 en todo control guardado entre 05/2026 y GI.1: imprimia «None» y «no pasa» con 6 de 6 ROI
visibles) y ponia la marca de aprobado en «Diametro minimo visible» por que hubiera un numero, no porque el control pasara; la de resolucion espacial rotulaba
«lp/mm» y leia `'lp/mm'` por region (None en los controles con el defecto de GI.1, 0.1 a 0.8 en los de enero a abril, 1.00 a 8.00 rotulado lp/mm en los nuevos) y
la maxima y la MTF de enero a abril (guardadas en lp/mm) salian rotuladas como lp/cm si alguien las leia por su nombre. «Ver tabla» de resolucion espacial rotulaba
«LP/mm Maximo» sobre una columna que desde GI.0 se llama `lp_cm_maximo` y que en enero a abril sigue en lp/mm.
Y las deudas de GI.2: un constructor de pantalla que lanzaba (un contraste o una visibilidad guardados como texto) dejaba la pestana muda, sin decir por que; la
tabla de Valores CT mostraba «N/A» en un promedio de 0 HU; y la copia de `tac_mensual.py` de cada constructor (seis, versiones viejas de las de `catphan_db`) mostraba
el analisis recien hecho distinto de lo reabierto.

GARANTIAS, una por bloque:

  1. LECTORES -- el diametro minimo visible guardado se entrega; las claves de transicion (`'lp/mm'` por region, `*_lim` del resumen) ya no existen; la maxima y la
     MTF de un control de enero a abril salen en lp/cm (×10), el centinela -1 no se convierte; sin conteo derivable el 0 guardado no es un veredicto.
  2. EL PDF IMPRIME -- lo que cada tabla dice en cada caso real (guardado, resumen NULL, enero a abril, defecto de GI.1, centinela), en lp/cm y con el veredicto de la prueba.
  3. NINGUN «None» NI MARCA EN EL PDF -- en las diez sesiones reales y con cada valor hostil en cada hoja de lo reabierto (None, texto, BLOB, 0, -1, inf, True).
  4. «VER TABLA» -- los encabezados llevan la unidad entre corchetes y la maxima y la MTF salen en lp/cm fila por fila, tambien en las diez sesiones reales.
  5. LAS PANTALLAS NO LANZAN -- cada constructor de pantalla con cada valor hostil en cada hoja y con nada (None); el analisis recien hecho (3 equipos) y lo reabierto
     se muestran con el mismo codigo (una sola definicion).
  6. UN FALLO DE PANTALLA SE DICE -- con `label`, la pestana de esa prueba dice la causa y las demas siguen; sin `label` la reapertura entera falla como siempre.
  7. TRIPWIRES por AST -- ningun «✓»/«✗» en el modulo del PDF (DA-18); `tac_mensual.py` no define constructores de tabla.

Nunca se conecta a una BD de referencia: las bases son nuevas o copias en un temporal.
"""
import ast
import copy
import os
import pathlib
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QDialog, QLabel, QTableWidget, QWidget

import data.ManejoDatos.load as load_mod
from data.ManejoDatos.catphan_TAC import catphan_db as C
from data.ManejoDatos.conection import Conexion
from test_gi1_guardado_claves_del_analisis import (  # noqa: F401  (helpers y fixtures de GI.1: una sola definicion de la forma del productor)
    _crear_control, _forma_linealidad, _guardar, _leer, _resultado_contraste, _resultado_espesor, _resultado_uniformidad, app, bd_nueva, base_real)
from _informe_imagenes import avisos, generar as _generar_informe, paginas as _paginas_del_informe  # noqa: F401  (el informe REAL, con el visor sustituido)
from test_gi2_lectura_es_lo_guardado import (  # noqa: F401  (helpers y fixtures de GI.2)
    CATPHAN_DB, ID_TIPO_INVERSO, PDF_IMAGENES, RAIZ, SESIONES_REALES, _celdas, _cerrar_la_base, _con_la_base, _ejecutar, _encabezados,
    _espacial_de_ocho_regiones, _filas_pdf, _forzar_resumen_de_contraste_nulo, _funciones, _guardar_espacial_antiguo, _materiales_ct, _pdf, _reabrir,
    bd_copia_real)

TAC_MENSUAL = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "tac_mensual.py"

# Lo que un valor guardado puede ser sin ser el numero que se espera: nada, un texto (SQLite admite texto en una columna REAL), el centinela del escritor, vacio,
# un BLOB, un cero, un negativo, el infinito, un booleano. (NaN no: SQLite lo guarda como NULL.)
HOSTILES = [None, "texto", "No disponible", "", b"\x01", 0, 0.0, -1, float("inf"), True]


# ---------------------------------------------------------------------------
# Ayudas
# ---------------------------------------------------------------------------

def _tabla(nombre, resultado, **kw):
    return _filas_pdf(getattr(_pdf(), "_crear_tabla_" + nombre)(resultado, **kw))


def _fila(filas, rotulo):
    return next(f for f in filas if f[0] == rotulo)


def _hojas(nodo, ruta=()):
    """(ruta, valor) de cada hoja escalar de un resultado reabierto (la imagen no)."""
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave != "imagen_analisis":
                yield from _hojas(valor, ruta + (clave,))
    elif isinstance(nodo, (list, tuple)):
        for i, valor in enumerate(nodo):
            yield from _hojas(valor, ruta + (i,))
    else:
        yield ruta, nodo


def _con_hoja(nodo, ruta, valor):
    """Copia de `nodo` con la hoja `ruta` sustituida por `valor` (las tuplas pasan a lista para poder asignar)."""
    copia = copy.deepcopy(nodo)
    padre = copia
    for paso in ruta[:-1]:
        if isinstance(padre[paso], tuple):
            nuevo = list(padre[paso])
            padre[paso] = nuevo
        padre = padre[paso]
    padre[ruta[-1]] = valor
    return copia


def _celdas_de_texto(tabla_df):
    return [str(c) for fila in tabla_df.values.tolist() for c in fila]


def _reapertura_completa(sesion):
    return C.reconstruir_resultados_desde_bd(sesion)


# ---------------------------------------------------------------------------
# 1. LECTORES
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("visibles, esperado", [((15, 9, 8, 7), 7), ((15, 9, 8), 8), ((15, 9, 8, 7, 6, 5), 5), ((), None)])
def test_el_lector_de_contraste_entrega_el_menor_roi_visible_guardado(bd_nueva, visibles, esperado):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste(visibles, (15, 9))}) == sesion
    assert _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]["diametro_minimo_visible"] == esperado


def test_un_diametro_minimo_guardado_como_texto_se_entrega_como_none(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7), (15, 9))}) == sesion
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste SET diametro_minimo_visible = 'No disponible'")
    assert _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]["diametro_minimo_visible"] is None


def test_el_lector_ya_no_entrega_las_claves_de_transicion(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6), (15, 9)),
                             "resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    resumen = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert not {k for k in resumen if k.endswith("_lim")}, sorted(resumen)
    for como, lp in (("nuevo", None), ("enero a abril", {f"region {n}": n / 10 for n in range(1, 9)}), ("defecto de GI.1", {f"region {n}": None for n in range(1, 9)})):
        if lp is not None:
            _guardar_espacial_antiguo(bd_nueva, sesion, "region 3", 0.3, lp, (None, None, 0.26))
        regiones = _reabrir(bd_nueva, "resolucion_espacial", sesion)["region_results"]
        assert all(set(r) >= {"lp/cm"} and "lp/mm" not in r for r in regiones.values()), como


def test_los_lectores_no_nombran_las_claves_de_transicion():
    """Por AST: ninguna cadena de los dos lectores es una clave de transicion (`rois_visibles_visibilidad_lim`, `pasa_test_visibilidad_lim`, `'lp/mm'` por region)."""
    funciones = _funciones(CATPHAN_DB)
    for nombre in ("reconstruir_resolucion_contraste", "reconstruir_resolucion_espacial"):
        cadenas = {n.value for n in ast.walk(funciones[nombre]) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        assert len(cadenas) > 10, f"{nombre}: el censo no examino el lector"
        assert not cadenas & {"rois_visibles_visibilidad_lim", "pasa_test_visibilidad_lim", "lp/mm"}, (nombre, sorted(cadenas & {"lp/mm"}))


@pytest.mark.parametrize("valor, unidad, esperado", [
    (0.3, "lp/mm", 3.0), (0.2628, "lp/mm", 2.628), (0.1, "lp/mm", 1.0), (0.8, "lp/mm", 8.0),     # sin ruido de coma flotante
    (3.0, "lp/cm", 3.0), (2.17, "lp/cm", 2.17),
    (-1, "lp/mm", -1), (-1, "lp/cm", -1), (0, "lp/mm", 0), (None, "lp/mm", None), (None, "lp/cm", None),   # el centinela, el cero y la ausencia no se convierten
])
def test_en_lp_cm_convierte_solo_una_frecuencia_positiva_guardada_en_lp_mm(valor, unidad, esperado):
    resultado = C.en_lp_cm(valor, unidad)
    assert resultado == esperado and type(resultado) is type(esperado)


def test_la_maxima_y_la_mtf_de_un_control_de_enero_a_abril_salen_en_lp_cm(bd_nueva):
    """El caso de la sesion 12 de la copia del 21-09 (guardo maxima 0.3 y MTF 50 % 0.2628): 3.0 y 2.628."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _guardar_espacial_antiguo(bd_nueva, sesion, "region 3", 0.3, {f"region {n}": n / 10 for n in range(1, 9)}, (0.1, 0.2, 0.2628))
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert r["unidad_guardada"] == "lp/mm"
    assert r["resolucion_limite"]["lp_cm_maximo"] == 3.0 and r["mtf_lp_cm"] == {"10": 1.0, "20": 2.0, "50": 2.628}


def test_el_centinela_de_ninguna_region_medible_no_se_convierte_ni_siquiera_en_una_fila_de_lp_mm(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _guardar_espacial_antiguo(bd_nueva, sesion, None, -1, {f"region {n}": n / 10 for n in range(1, 9)}, (None, None, None))
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert r["unidad_guardada"] == "lp/mm" and r["resolucion_limite"]["lp_cm_maximo"] == -1 and r["mtf_lp_cm"] == {}


def test_un_control_nuevo_en_lp_cm_no_se_multiplica(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert r["unidad_guardada"] == "lp/cm" and r["resolucion_limite"]["lp_cm_maximo"] == 3 and r["mtf_lp_cm"] == {"50": 2.6}


# ---------------------------------------------------------------------------
# 2. LO QUE EL PDF IMPRIME
# ---------------------------------------------------------------------------

def test_el_pdf_de_uniformidad_imprime_el_hu_de_cada_region_y_dice_n_a_lo_que_no_hay(bd_nueva):
    analisis = _resultado_uniformidad(True, True)
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": analisis}) == sesion
    filas = _tabla("uniformidad", _reabrir(bd_nueva, "uniformidad", sesion))
    assert filas[0] == ["Región", "HU promedio", "Desviación estándar"]
    for nombre in ("Centro", "Arriba", "Derecha", "Abajo", "Izquierda"):
        assert _fila(filas, nombre)[1:] == [f"{analisis[nombre]['promedio_hu']:.1f}", f"{analisis[nombre]['desviacion']:.2f}"], nombre
    # un ROI guardado como el texto del escritor: el lector lo da None y el informe lo dice N/A (nunca «None»)
    _ejecutar(bd_nueva, "UPDATE uniformidad_ruido SET hu_promedio = 'No disponible' WHERE id_region = 2")
    filas = _tabla("uniformidad", _reabrir(bd_nueva, "uniformidad", sesion))
    assert _fila(filas, "Arriba")[1] == "N/A"


def test_el_pdf_de_uniformidad_dice_n_a_en_las_metricas_globales_nulas(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": _resultado_uniformidad(True, True)}) == sesion
    reabierta = _reabrir(bd_nueva, "uniformidad", sesion)
    reabierta["Uniformidad"].update(max_diferencia=None, desviacion_global=None, uniformity_index_max=None, integral_non_uniformity_pct=None, pasa_global=None)
    for con_criterio, rotulo in ((False, "Pasa prueba de uniformidad"), (True, "UI/INU con el umbral heredado (informativo)")):
        filas = _tabla("uniformidad", reabierta, con_criterio=con_criterio)
        assert [_fila(filas, r)[1] for r in ("Diferencia máxima entre regiones" if con_criterio else "Diferencia máxima", "Desviación global",
                                              "Uniformity Index (UI)", "Integral Non-Uniformity (INU)", rotulo)] == ["N/A"] * 5


@pytest.mark.parametrize("pasa_ui, pasa_inu, esperado", [(True, True, "Sí"), (True, False, "No"), (False, True, "No"), (False, False, "No")])
def test_el_pdf_de_uniformidad_dice_si_o_no_en_palabras(bd_nueva, pasa_ui, pasa_inu, esperado):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": _resultado_uniformidad(pasa_ui, pasa_inu)}) == sesion
    r = _reabrir(bd_nueva, "uniformidad", sesion)
    assert _fila(_tabla("uniformidad", r), "Pasa prueba de uniformidad")[1] == esperado
    assert _fila(_tabla("uniformidad", r, con_criterio=True), "UI/INU con el umbral heredado (informativo)")[1] == esperado


@pytest.mark.parametrize("resumen_nulo, visibles, conteo, veredicto, diametro", [
    (False, (15, 9, 8, 7, 6), "5", "Sí", "6"),         # guardado: 5 visibles y pasa
    (False, (15, 9, 8), "3", "No", "8"),                # guardado: 3 visibles y NO pasa -- el diametro existe (8) y la marca NO es de aprobado: el veredicto, no la presencia
    (True, (15, 9, 8, 7, 6, 5), "6", "Sí", "5"),        # NULL (defecto de GI.1): conteo y veredicto derivados del detalle (la sesion 48 real)
    (True, (15, 9), "2", "No", "9"),                    # NULL con el detalle completo y pocos visibles: 2 y no pasa
    (False, (), "0", "No", "N/A"),                      # ningun ROI visible: 0, no pasa y sin diametro
])
def test_el_pdf_de_contraste_imprime_el_conteo_el_veredicto_y_el_diametro(bd_nueva, resumen_nulo, visibles, conteo, veredicto, diametro):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste(visibles, (15, 9))}) == sesion
    if resumen_nulo:
        _forzar_resumen_de_contraste_nulo(bd_nueva)
    filas = _tabla("resolucion_contraste", _reabrir(bd_nueva, "resolucion_contraste", sesion))
    assert _fila(filas, "ROIs visibles")[1:] == [conteo, veredicto]
    assert _fila(filas, "Diámetro mínimo visible [mm]")[1:] == [diametro, veredicto], "la marca de esta fila es el veredicto de la prueba, no «hay un numero»"


def test_el_pdf_de_contraste_dice_n_a_el_conteo_y_el_veredicto_que_nadie_midio(bd_nueva):
    """(conteo NULL, veredicto 0) sin detalle por ROI es la firma del defecto de GI.1, no un «no pasa»: el informe firmado dice N/A en las dos filas."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6), (15, 9))}) == sesion
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    _ejecutar(bd_nueva, "DELETE FROM resolucion_contraste_rois")
    filas = _tabla("resolucion_contraste", _reabrir(bd_nueva, "resolucion_contraste", sesion))
    assert _fila(filas, "ROIs visibles")[1:] == ["N/A", "N/A"]
    assert _fila(filas, "Diámetro mínimo visible [mm]")[1:] == ["6", "N/A"]


def test_el_pdf_de_contraste_dice_si_o_no_por_roi_y_n_a_si_no_hay_veredicto(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8), (15, 9))}) == sesion
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste_rois SET pasa_visibilidad_lim = NULL WHERE diametro_mm = 5")
    filas = _tabla("resolucion_contraste", _reabrir(bd_nueva, "resolucion_contraste", sesion))
    assert filas[0] == ["Diámetro ROI [mm]", "Visibilidad", "Pasa Visibilidad"]
    por_diametro = {f[0]: f[2] for f in filas[1:7]}
    assert por_diametro == {"15": "Sí", "9": "Sí", "8": "Sí", "7": "No", "6": "No", "5": "N/A"}
    assert [f[1] for f in filas[1:7]] == ["0.21", "0.22", "0.23", "0.24", "0.25", "0.26"], "la visibilidad de cada ROI se imprime con dos decimales"


@pytest.mark.parametrize("como, lp_por_region, maximo, ultima, mtf, regiones_lp_cm, maxima, mtf10, mtf50", [
    ("nuevo", None, None, None, None, ["1.00", "2.00", "3.00"], "3.00", "N/A", "2.60"),
    ("enero a abril", {f"region {n}": n / 10 for n in range(1, 9)}, 0.3, "region 3", (None, None, 0.2628), ["1.00", "2.00", "3.00"], "3.00", "N/A", "2.63"),
    ("defecto de GI.1", {f"region {n}": None for n in range(1, 9)}, 3.0, "region 3", (None, 2.87, 2.17), ["1.00", "2.00", "3.00"], "3.00", "N/A", "2.17"),
    ("enero a abril con MTF 10", {f"region {n}": n / 10 for n in range(1, 9)}, 0.3, "region 3", (0.1234, None, 0.2628), ["1.00", "2.00", "3.00"], "3.00", "1.23", "2.63"),
])
def test_el_pdf_de_resolucion_espacial_imprime_lp_cm_en_cada_caso_real(bd_nueva, como, lp_por_region, maximo, ultima, mtf, regiones_lp_cm, maxima, mtf10, mtf50):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    if lp_por_region is not None:
        _guardar_espacial_antiguo(bd_nueva, sesion, ultima, maximo, lp_por_region, mtf)
    filas = _tabla("resolucion_espacial", _reabrir(bd_nueva, "resolucion_espacial", sesion))
    assert filas[0] == ["Región", "Frecuencia [lp/cm]", "Gap size [cm]", "Picos", "Valles", "Estado"], como
    assert [f[1] for f in filas[1:4]] == regiones_lp_cm, como
    assert _fila(filas, "Resolución máxima")[1] == maxima and _fila(filas, "Resolución máxima")[5] == "region 3", como
    assert _fila(filas, "MTF 10%")[1] == mtf10 and _fila(filas, "MTF 50%")[1] == mtf50, como


def test_el_pdf_de_resolucion_espacial_dice_n_a_en_lo_que_el_analisis_no_midio(bd_nueva):
    """Gap, Picos, Valles y Estado de una region que el analisis no midio: «N/A» (antes «None»); el Estado que el analisis si dio se imprime."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _ejecutar(bd_nueva, "UPDATE resolucion_espacial_regiones SET status = NULL WHERE region_nombre = 'region 8'")
    filas = {f[0]: f for f in _tabla("resolucion_espacial", _reabrir(bd_nueva, "resolucion_espacial", sesion))}
    assert filas["region 1"][2:] == ["0.5000", "3", "2", "OK"]
    assert filas["region 4"][2:] == ["N/A", "N/A", "N/A", "Picos insuficientes"]
    assert filas["region 8"][2:] == ["N/A", "N/A", "N/A", "N/A"] and filas["region 8"][1] == "8.00"


def test_el_pdf_de_resolucion_espacial_dice_sin_region_medible_con_el_centinela(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _guardar_espacial_antiguo(bd_nueva, sesion, None, -1, {f"region {n}": None for n in range(1, 9)}, (None, None, None))
    filas = _tabla("resolucion_espacial", _reabrir(bd_nueva, "resolucion_espacial", sesion))
    assert _fila(filas, "Resolución máxima")[1::4] == ["Sin región medible", "N/A"]
    assert _fila(filas, "MTF 50%")[1] == "N/A"


def test_el_pdf_de_tamano_de_pixel_dice_n_a_donde_la_base_no_trae_el_valor(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"tamano_pixel": {"X": 0.982, "Y": 0.963, "imagen_analisis": None}}, tam_px_teorico=0.959) == sesion
    _ejecutar(bd_nueva, 'UPDATE "tamaño_pixel" SET valor_teorico_dicom = NULL, diferencia_x = NULL')
    filas = _tabla("tamano_pixel", _reabrir(bd_nueva, "tamano_pixel", sesion))
    assert [_fila(filas, r)[1] for r in ("Tamaño teórico", "Diferencia X")] == ["N/A", "N/A"] and _fila(filas, "X medido")[1] == "0.982 mm"


def test_el_pdf_de_espesor_dice_n_a_en_lo_que_falta():
    filas = _tabla("espesor_corte", {"espesor_promedio_mm": 2.5, "espesor_teorico_mm": None, "diferencia_mm": None})
    assert [_fila(filas, r)[1] for r in ("Espesor promedio medido", "Espesor teórico", "Diferencia")] == ["2.500 mm", "N/A", "N/A"]


def test_el_pdf_de_valores_ct_conserva_el_texto_del_error_relativo_y_dice_n_a_a_lo_que_falta(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"valores_ct": _materiales_ct(False)}) == sesion
    _ejecutar(bd_nueva, "UPDATE valores_ct SET error_relativo = 'Fuera de Rango' WHERE id_material = 1")
    reabierto = _reabrir(bd_nueva, "valores_ct", sesion)
    reabierto[1]["error_abs"] = None                  # la columna del escritor es NOT NULL: aqui se prueba el constructor con lo que un lector pudiera entregar
    celdas = [c for f in _tabla("valores_ct", reabierto) for c in f]
    assert "Fuera de Rango" in celdas and "N/A" in celdas and "None" not in celdas


def test_el_pdf_de_linealidad_dice_en_palabras_y_n_a(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"linealidad_ct": _forma_linealidad(0.9999)}) == sesion
    r = _reabrir(bd_nueva, "linealidad_ct", sesion)
    assert _fila(_tabla("linealidad_ct", r), "Linealidad aceptable (R²≥0.99)")[1] == "Sí"
    _ejecutar(bd_nueva, "UPDATE linealidad_ct SET pendiente = NULL, intercepto = NULL, escala_contraste = NULL, linealidad_aceptable = 0")
    r = _reabrir(bd_nueva, "linealidad_ct", sesion)
    filas = _tabla("linealidad_ct", r)
    assert [_fila(filas, x)[1] for x in ("Pendiente", "Intercepto", "Escala de contraste", "Linealidad aceptable (R²≥0.99)")] == ["N/A", "N/A", "N/A", "No"]


def test_el_pdf_no_dice_none_ni_lanza_con_una_region_sin_nombre_ni_con_un_r_gigante(bd_nueva):
    filas = _tabla("resolucion_espacial", {"region_results": {None: {"lp/cm": 1.0, "status": "OK"}}, "resolucion_limite": {}, "mtf_lp_cm": {}, "unidad_guardada": "lp/cm"})
    assert not [c for fila in filas for c in fila if "None" in str(c)] and ["N/A", "1.00"] == filas[1][:2]
    filas = _tabla("linealidad_ct", {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 1e300, "linealidad_aceptable": True}, con_criterio=True)
    assert _fila(filas, "R² (r al cuadrado)")[1] == "N/A"          # r ** 2 desbordaba (OverflowError) y tumbaba el informe


@pytest.mark.parametrize("valor, esperado", [(b"\x00", False), (b"\x01", True), ("No", False), ("no", False), ("Sí", True), ("0", False), ("1", True), ("false", False),
                                             ("texto raro", None), ("", None), (None, None), (0, False), (1, True)])
def test_la_bandera_guardada_como_blob_o_texto_se_lee_por_lo_que_dice(valor, esperado):
    """Una sola definicion de como se lee una bandera: bool(b'\\x00') y bool('No') son True; el lector y el PDF la usan."""
    assert C._bandera_guardada(valor) is esperado


@pytest.mark.parametrize("guardado, veredicto", [("X'00'", "No"), ("X'01'", "Sí"), ("'No'", "No"), ("'Sí'", "Sí"), ("'texto raro'", "N/A"), ("0", "No"), ("1", "Sí")])
def test_el_veredicto_de_contraste_guardado_como_blob_o_texto_se_imprime_por_lo_que_dice(bd_nueva, guardado, veredicto):
    """El lector aplicaba `bool()` antes de que el PDF decodificara: un BLOB `\\x00` o el texto «No» salian «Sí»."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6), (15, 9))}) == sesion
    _ejecutar(bd_nueva, f"UPDATE resolucion_contraste SET pasa_test_visibilidad = {guardado}")
    filas = _tabla("resolucion_contraste", _reabrir(bd_nueva, "resolucion_contraste", sesion))
    assert _fila(filas, "ROIs visibles")[1:] == ["5", veredicto] and _fila(filas, "Diámetro mínimo visible [mm]")[2] == veredicto


def test_los_roi_guardados_como_blob_cero_no_cuentan_como_visibles(bd_nueva):
    """Con el conteo NULL el lector lo deriva del detalle por ROI: seis banderas BLOB `\\x00` son seis «no», no seis «verdadero»."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6, 5), (15, 9))}) == sesion
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste_rois SET pasa_visibilidad_lim = X'00'")
    filas = _tabla("resolucion_contraste", _reabrir(bd_nueva, "resolucion_contraste", sesion))
    assert _fila(filas, "ROIs visibles")[1:] == ["0", "No"] and {f[2] for f in filas[1:7]} == {"No"}
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste_rois SET pasa_visibilidad_lim = 'texto raro'")
    filas = _tabla("resolucion_contraste", _reabrir(bd_nueva, "resolucion_contraste", sesion))
    assert {f[2] for f in filas[1:7]} == {"N/A"}


@pytest.mark.parametrize("energia, esperado", [(0.12, "0.12"), (6, "6"), (None, "no registrada"), (float("inf"), "no registrada"), (True, "no registrada"), ("texto", "no registrada")])
def test_el_pdf_de_linealidad_dice_la_energia_o_que_no_esta_registrada(energia, esperado):
    filas = _tabla("linealidad_ct", {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 0.999, "linealidad_aceptable": True, "energia_mev": energia})
    assert _fila(filas, "Energía [MeV]")[1].startswith(esperado), filas


def test_las_pantallas_de_tamano_de_pixel_y_uniformidad_no_dicen_none_donde_la_base_no_trae_el_valor(reapertura_de_ejemplo):
    texto = C.tabla_resultados_tamano_pixel({"X": None, "Y": None, "tam_px_teorico": 0.5})
    assert "X: N/A mm" in texto and "Y: N/A mm" in texto and "None" not in texto
    base = copy.deepcopy(reapertura_de_ejemplo["uniformidad"])
    base["Uniformidad"]["desviacion_global"] = None
    contenedor = C.tabla_resultados_uniformidad(base)                                  # se conserva: la tabla puede ser hija del contenedor
    tabla = contenedor if isinstance(contenedor, QTableWidget) else contenedor.findChild(QTableWidget)
    celdas = [c for fila in _celdas(tabla) for c in fila]
    assert any(c and "Desv. global: N/A" in c for c in celdas) and not any(c and "None" in c for c in celdas)


# --- los casos de las sesiones REALES (copia de la BD del 21-09) ---

def test_la_sesion_12_real_imprime_3_00_y_2_63_en_lp_cm(bd_copia_real):
    """El caso de verificacion del plan: la sesion 12 (enero a abril, guardada en lp/mm: maxima 0.3, MTF 50 % 0.2628) debe decir 3.00 y 2.63, no 0.30 y 0.26."""
    r = C.reconstruir_resultados_desde_bd(12, categorias=["resolucion_espacial"])["resolucion_espacial"]
    assert r["unidad_guardada"] == "lp/mm"
    filas = _tabla("resolucion_espacial", r)
    assert _fila(filas, "Resolución máxima")[1] == "3.00" and _fila(filas, "MTF 50%")[1] == "2.63"
    assert [f[1] for f in filas[1:4]] == ["1.00", "2.00", "3.00"]


def test_la_sesion_48_real_imprime_6_y_si_donde_el_pdf_decia_none_y_no(bd_copia_real):
    filas = _tabla("resolucion_contraste", C.reconstruir_resultados_desde_bd(48, categorias=["resolucion_contraste"])["resolucion_contraste"])
    assert _fila(filas, "ROIs visibles")[1:] == ["6", "Sí"]


def test_el_pdf_de_las_diez_sesiones_reales_no_dice_none_nan_ni_marcas(bd_copia_real):
    """Las siete tablas de cada sesion real: ninguna celda dice «None», «nan» ni una marca de correcto/incorrecto (DA-18)."""
    examinadas = 0
    for sesion in SESIONES_REALES:
        todo = _reapertura_completa(sesion)
        for categoria, resultado in todo.items():
            if categoria == "uniformidad":
                variantes = [dict(), dict(con_criterio=True)]
            elif categoria == "linealidad_ct":
                variantes = [dict(), dict(con_criterio=True)]
            else:
                variantes = [dict()]
            for kw in variantes:
                celdas = _celdas_de_texto(getattr(_pdf(), "_crear_tabla_" + {"espesor": "espesor_corte"}.get(categoria, categoria))(resultado, **kw))
                malas = [c for c in celdas if "None" in c or "nan" in c.lower().split() or "✓" in c or "✗" in c]
                assert not malas, (sesion, categoria, malas)
                examinadas += 1
    assert examinadas >= 60


def _equipo_y_fecha(ruta, sesion):
    con = _leer(ruta)
    try:
        fila = con.execute("SELECT equipo, fecha FROM controles WHERE id = ?", (sesion,)).fetchone()
    finally:
        con.close()
    return fila["equipo"], fila["fecha"]


def test_el_informe_pdf_de_la_sesion_12_dice_3_00_y_2_63(bd_copia_real, monkeypatch, avisos):
    """De punta a punta: el informe REAL de la sesion 12 (no los constructores sueltos)."""
    equipo, fecha = _equipo_y_fecha(bd_copia_real, 12)
    ok, recibido = _generar_informe(bd_copia_real, monkeypatch, 12, equipo, fecha)
    assert ok and not avisos, avisos
    texto = "\n".join(_paginas_del_informe(recibido["pdf"]))
    plano = " ".join(texto.split())                                   # las celdas largas se parten en lineas en el PDF
    assert "Frecuencia [lp/cm]" in plano
    resumen = plano.split("Resolución máxima")[1]
    assert resumen.startswith(" 3.00") and "MTF 50% 2.63" in resumen and "0.30" not in resumen[:30]


@pytest.mark.parametrize("sesion, conteo, veredicto", [(21, "3", "No"), (48, "6", "Sí")])
def test_el_informe_pdf_real_imprime_el_conteo_y_el_veredicto_de_los_rois_visibles(bd_copia_real, monkeypatch, avisos, sesion, conteo, veredicto):
    """De punta a punta: en el informe REAL el renglon «ROIs visibles» dice el conteo Y el veredicto (el generador compartido fundia esas dos columnas con SPAN y el veredicto
    desaparecia del PDF mensual)."""
    equipo, fecha = _equipo_y_fecha(bd_copia_real, sesion)
    ok, recibido = _generar_informe(bd_copia_real, monkeypatch, sesion, equipo, fecha)
    assert ok and not avisos, avisos
    plano = " ".join("\n".join(_paginas_del_informe(recibido["pdf"])).split())
    assert "ROIs visibles" in plano
    assert plano.split("ROIs visibles")[1].lstrip().startswith(f"{conteo} {veredicto}"), plano.split("ROIs visibles")[1][:40]


# ---------------------------------------------------------------------------
# 3. NINGUN «None» NI MARCA EN EL PDF: cada valor hostil en cada hoja
# ---------------------------------------------------------------------------

CONSTRUCTORES_PDF = {"espesor": "espesor_corte", "tamano_pixel": "tamano_pixel", "resolucion_contraste": "resolucion_contraste",
                     "resolucion_espacial": "resolucion_espacial", "valores_ct": "valores_ct", "linealidad_ct": "linealidad_ct", "uniformidad": "uniformidad"}


@pytest.fixture(scope="module")
def reapertura_de_ejemplo(app, tmp_path_factory):
    """Lo reabierto de una sesion con las siete categorias (la forma de los lectores), de una BD nueva. No mantiene la base abierta: se guarda, se lee y se suelta."""
    import data.ManejoDatos.conection as conection_mod
    ruta = str(tmp_path_factory.mktemp("gi3") / "ejemplo.db")
    mp = pytest.MonkeyPatch()
    mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    Conexion()
    try:
        sesion = _crear_control(ruta)
        assert _guardar(sesion, {"espesor": _resultado_espesor(2.5), "tamano_pixel": {"X": 0.982, "Y": 0.963, "imagen_analisis": None},
                                 "resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6), (15, 9)), "resolucion_espacial": _espacial_de_ocho_regiones(),
                                 "valores_ct": _materiales_ct(True), "linealidad_ct": _forma_linealidad(0.9999),
                                 "uniformidad": _resultado_uniformidad(True, True)}, espesor_corte=2.0, tam_px_teorico=0.959) == sesion
        return {c: _reabrir(ruta, c, sesion) for c in CONSTRUCTORES_PDF}
    finally:
        _cerrar_la_base()
        mp.undo()


@pytest.mark.parametrize("categoria", sorted(CONSTRUCTORES_PDF))
def test_el_pdf_no_lanza_ni_dice_none_con_ningun_valor_hostil_en_ninguna_hoja(reapertura_de_ejemplo, categoria):
    base = reapertura_de_ejemplo[categoria]
    constructor = getattr(_pdf(), "_crear_tabla_" + CONSTRUCTORES_PDF[categoria])
    variantes = [dict(), dict(con_criterio=True)] if categoria in ("uniformidad", "linealidad_ct") else [dict()]
    hojas = list(_hojas(base))
    assert len(hojas) >= 4, f"{categoria}: el censo de hojas no examino nada"
    malas, casos = [], 0
    for ruta, _ in hojas:
        for hostil in HOSTILES:
            variante = _con_hoja(base, ruta, hostil)
            for kw in variantes:
                casos += 1
                try:
                    celdas = _celdas_de_texto(constructor(variante, **kw))
                except Exception as e:                                  # noqa: BLE001
                    malas.append((ruta, hostil, f"{type(e).__name__}: {e}"))
                    continue
                if any(c == "None" or "✓" in c or "✗" in c for c in celdas):
                    malas.append((ruta, hostil, "None o marca"))
    assert casos >= 40
    assert not malas, f"{categoria}: {len(malas)} de {casos} casos: {malas[:6]}"


def test_el_pdf_con_nada_no_lanza(app):
    for nombre in CONSTRUCTORES_PDF.values():
        constructor = getattr(_pdf(), "_crear_tabla_" + nombre)
        for vacio in ([[], [{}]] if nombre == "valores_ct" else [{}, {"resumen": {}, "resultados_roi": {}}, {"region_results": {}}]):
            try:
                constructor(vacio)
            except Exception as e:                                       # noqa: BLE001
                raise AssertionError(f"{nombre} lanza con {vacio!r}: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 4. «VER TABLA» DE RESOLUCION ESPACIAL
# ---------------------------------------------------------------------------

@pytest.fixture
def dialogos(monkeypatch):
    """Sustituye `QDialog.exec_` por una captura: `_mostrar_tabla_generica` no se queda esperando una persona (Trampa 2)."""
    capturados = []
    monkeypatch.setattr(QDialog, "exec_", lambda self: capturados.append(self) or 0)
    return capturados


def _tabla_del_dialogo(dialogo):
    tabla = dialogo.findChild(QTableWidget)
    assert tabla is not None, "el dialogo no trae tabla: " + " ".join(l.text() for l in dialogo.findChildren(QLabel))
    return _encabezados(tabla), _celdas(tabla)


def test_ver_tabla_de_resolucion_espacial_rotula_la_unidad_entre_corchetes(bd_copia_real, dialogos):
    load_mod.mostrar_resolucion_espacial(None, 12)
    encabezados, _ = _tabla_del_dialogo(dialogos[0])
    assert "Resolución Máxima [lp/cm]" in encabezados and "MTF 10% [lp/cm]" in encabezados and "MTF 50% [lp/cm]" in encabezados
    assert "Gap Size Mínimo [cm]" in encabezados
    assert not [e for e in encabezados if "(" in e or "LP/mm" in e], encabezados


def test_ver_tabla_de_la_sesion_12_muestra_la_maxima_y_la_mtf_en_lp_cm(bd_copia_real, dialogos):
    load_mod.mostrar_resolucion_espacial(None, 12)
    encabezados, celdas = _tabla_del_dialogo(dialogos[0])
    fila = dict(zip(encabezados, celdas[0]))
    assert fila["Resolución Máxima [lp/cm]"] == "3.0" and fila["MTF 50% [lp/cm]"] == "2.627968", fila         # guardo 0.2627968 lp/mm
    assert fila["Última Región Exitosa"] == "region 3"


def test_ver_tabla_de_las_sesiones_reales_convierte_solo_las_de_lp_mm(bd_copia_real, dialogos):
    """Oraculo independiente: una maxima entre 0 y 1 solo puede ser lp/mm (la region 1 vale 1 lp/cm); lo demas (lp/cm y el centinela) se muestra como se guardo."""
    con = _leer(bd_copia_real)
    try:
        filas_sql = {r["id_sesion"]: r for r in con.execute(
            "SELECT p.id_sesion, e.lp_cm_maximo, e.mtf_10_pct, e.mtf_20_pct, e.mtf_50_pct FROM resolucion_espacial e JOIN pruebas p ON p.id_prueba = e.id_prueba "
            "WHERE (e.activo IS NULL OR e.activo = 1) AND (p.activo IS NULL OR p.activo = 1)")}
    finally:
        con.close()
    en_lp_mm = en_lp_cm = 0
    for sesion, sql in filas_sql.items():
        dialogos.clear()
        load_mod.mostrar_resolucion_espacial(None, sesion)
        encabezados, celdas = _tabla_del_dialogo(dialogos[0])
        fila = dict(zip(encabezados, celdas[0]))
        factor = 10 if sql["lp_cm_maximo"] is not None and 0 < sql["lp_cm_maximo"] < 1 else 1
        en_lp_mm += factor == 10
        en_lp_cm += factor == 1
        # «Ver tabla» y el lector del PDF deducen la unidad por caminos distintos (la maxima contra la ultima region / las regiones): en cada fila real dicen lo mismo
        assert C.reconstruir_resultados_desde_bd(sesion, categorias=["resolucion_espacial"])["resolucion_espacial"]["unidad_guardada"] == ("lp/mm" if factor == 10 else "lp/cm"), sesion
        for columna, clave in (("Resolución Máxima [lp/cm]", "lp_cm_maximo"), ("MTF 10% [lp/cm]", "mtf_10_pct"), ("MTF 20% [lp/cm]", "mtf_20_pct"),
                               ("MTF 50% [lp/cm]", "mtf_50_pct")):
            valor = sql[clave]
            esperado = "" if valor is None else str(round(valor * factor, 6) if factor == 10 else valor)
            assert fila[columna] == esperado, (sesion, columna, fila[columna], esperado)
    assert en_lp_mm >= 2 and en_lp_cm >= 4, (en_lp_mm, en_lp_cm)


@pytest.mark.parametrize("unidad, ultima, maximo, regiones, mtf, esperado", [
    ("lp/mm", "region 3", 0.3, {f"region {n}": n / 10 for n in range(1, 9)}, (0.1234, 0.2345, 0.2628), ("3.0", "1.234", "2.345", "2.628")),   # enero a abril: ×10 las tres MTF
    ("lp/cm", "region 3", 3.0, {f"region {n}": float(n) for n in range(1, 9)}, (1.5, 2.5, 2.6), ("3.0", "1.5", "2.5", "2.6")),                # control nuevo: tal cual
    ("lp/cm", None, -1, {f"region {n}": float(n) for n in range(1, 9)}, (None, None, None), ("-1.0", "", "", "")),                            # el centinela se muestra como se guardo
])
def test_ver_tabla_convierte_la_maxima_y_las_tres_mtf_de_una_fila_sintetica(bd_nueva, dialogos, unidad, ultima, maximo, regiones, mtf, esperado):
    """Las filas REALES en lp/mm solo traen la MTF 50 %: la 10 % y la 20 % solo se fijan con filas sinteticas."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _guardar_espacial_antiguo(bd_nueva, sesion, ultima, maximo, regiones, mtf)
    load_mod.mostrar_resolucion_espacial(None, sesion)
    encabezados, celdas = _tabla_del_dialogo(dialogos[0])
    fila = dict(zip(encabezados, celdas[0]))
    assert (fila["Resolución Máxima [lp/cm]"], fila["MTF 10% [lp/cm]"], fila["MTF 20% [lp/cm]"], fila["MTF 50% [lp/cm]"]) == esperado, (unidad, fila)
    assert C.reconstruir_resultados_desde_bd(sesion, categorias=["resolucion_espacial"])["resolucion_espacial"]["unidad_guardada"] == unidad


def test_el_visor_generico_no_cambia_para_las_otras_tablas(bd_copia_real, dialogos):
    """El gancho `filas` es opcional: `mostrar_valores_ct` (sin gancho) muestra lo que la base trae, fila por fila."""
    load_mod.mostrar_valores_ct(None, 12)
    encabezados, celdas = _tabla_del_dialogo(dialogos[0])
    con = _leer(bd_copia_real)
    try:
        n = con.execute("SELECT COUNT(*) FROM valores_ct v JOIN pruebas p ON p.id_prueba = v.id_prueba WHERE p.id_sesion = 12 AND (v.activo IS NULL OR v.activo = 1) "
                        "AND (p.activo IS NULL OR p.activo = 1)").fetchone()[0]
    finally:
        con.close()
    assert encabezados[0] == "ID Prueba" and len(celdas) == n == 7


# ---------------------------------------------------------------------------
# 5. LAS PANTALLAS NO LANZAN; LO RECIEN ANALIZADO Y LO REABIERTO SE MUESTRAN CON EL MISMO CODIGO
# ---------------------------------------------------------------------------

CONSTRUCTORES_PANTALLA = {"espesor": "tabla_resultados_espesor", "tamano_pixel": "tabla_resultados_tamano_pixel",
                          "resolucion_contraste": "tabla_resultados_resolucion_contraste", "resolucion_espacial": "tabla_resultados_resolucion_espacial",
                          "valores_ct": "tabla_resultados_ct", "linealidad_ct": "tabla_resultados_linealidad_ct", "uniformidad": "tabla_resultados_uniformidad"}


@pytest.mark.parametrize("categoria", sorted(CONSTRUCTORES_PANTALLA))
def test_la_pantalla_no_lanza_con_ningun_valor_hostil_en_ninguna_hoja(reapertura_de_ejemplo, categoria):
    base = reapertura_de_ejemplo[categoria]
    constructor = getattr(C, CONSTRUCTORES_PANTALLA[categoria])
    hojas = list(_hojas(base))
    assert len(hojas) >= 4
    malas, casos = [], 0
    for ruta, _ in hojas:
        for hostil in HOSTILES:
            casos += 1
            try:
                constructor(_con_hoja(base, ruta, hostil))
            except Exception as e:                                       # noqa: BLE001
                malas.append((ruta, hostil, f"{type(e).__name__}: {e}"))
    assert casos >= 40
    assert not malas, f"{categoria}: {len(malas)} de {casos} casos: {malas[:6]}"


@pytest.mark.parametrize("categoria", sorted(CONSTRUCTORES_PANTALLA))
def test_la_pantalla_sin_resultados_lo_dice_y_no_lanza(app, categoria):
    constructor = getattr(C, CONSTRUCTORES_PANTALLA[categoria])
    for vacio in (None, {}, []):
        contenido = constructor(vacio)
        texto = contenido if isinstance(contenido, str) else " ".join(l.text() for l in ([contenido] if isinstance(contenido, QLabel) else contenido.findChildren(QLabel)))
        assert "No hay resultados" in texto, (categoria, vacio, texto[:80])


def test_la_pantalla_de_contraste_dice_el_texto_guardado_y_no_lanza(reapertura_de_ejemplo):
    base = copy.deepcopy(reapertura_de_ejemplo["resolucion_contraste"])
    roi = base["resultados_roi"]["15mm"]
    roi["contraste_michelson"], roi["visibilidad_lim"], roi["diametro_mm"] = "No disponible", "texto", "quince"
    contenedor = C.tabla_resultados_resolucion_contraste(base)                       # se conserva: la tabla es hija del contenedor
    celdas = [c for fila in _celdas(contenedor.findChild(QTableWidget)) for c in fila]
    assert "No disponible" in celdas and "texto" in celdas and "quince" in celdas


def test_la_pantalla_de_contraste_dice_el_umbral_del_analisis_fresco_y_na_en_lo_reabierto(bd_nueva):
    """El umbral de visibilidad lo entrega el analisis recien hecho (`resumen['visibilidad_lim']`; la pantalla leia una clave que ningun analisis produce) y la base no
    lo guarda: lo reabierto dice «N/A» (D4: lo que no se guarda no se inventa)."""
    def etiquetas(contenedor):
        return " ".join(etiqueta.text() for etiqueta in contenedor.findChildren(QLabel))
    fresco = C.tabla_resultados_resolucion_contraste(_resultado_contraste((15, 9, 8, 7, 6), (15, 9)))
    assert "Umbral: 0.1" in etiquetas(fresco)
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6), (15, 9))}) == sesion
    reabierto = C.tabla_resultados_resolucion_contraste(_reabrir(bd_nueva, "resolucion_contraste", sesion))
    assert "Umbral: N/A" in etiquetas(reabierto)


def test_la_pantalla_de_valores_ct_muestra_un_promedio_de_cero(app):
    celdas = _celdas(C.tabla_resultados_ct([{"material": "Agua", "promedio_hu": 0.0, "rango_hu": [-5.0, 5.0], "error_abs": 0.0, "error_rel": 0.0}]))
    assert celdas[0][:3] == ["Agua", "0.0", "-5.0 a 5.0"], celdas


@pytest.mark.parametrize("rango", [None, "texto", [1], [1, 2, 3], (None, 5), 7])
def test_la_pantalla_de_valores_ct_con_un_rango_que_no_es_un_par_dice_n_a(app, rango):
    celdas = _celdas(C.tabla_resultados_ct([{"material": "Agua", "promedio_hu": 1.0, "rango_hu": rango, "error_abs": 1, "error_rel": 2}]))
    assert celdas[0][2] == "N/A", celdas


def test_el_pdf_de_contraste_ordena_los_diametros_con_decimales():
    roi = {"visibilidad_lim": 0.5, "pasa_visibilidad_lim": True}
    filas = _tabla("resolucion_contraste", {"resultados_roi": {"2.5mm": roi, "10mm": roi, "7.5mm": roi}, "resumen": {}})
    assert [f[0] for f in filas[1:4]] == ["10", "7.5", "2.5"]


def test_la_pantalla_de_valores_ct_rotula_el_error_absoluto(app):
    tabla = C.tabla_resultados_ct([{"material": "Aire", "promedio_hu": -990.0, "rango_hu": [-1060, -940], "error_abs": 10.0, "error_rel": "Dentro de rango"}])
    assert _encabezados(tabla) == ["Material", "Promedio HU", "Rango HU Ref.", "Error Abs. [HU]", "Rango"]


def test_lo_recien_analizado_y_lo_reabierto_tienen_los_mismos_encabezados_y_el_mismo_numero_de_filas(base_real):
    """El analisis REAL de cada equipo, mostrado como lo muestra la pantalla de un analisis recien hecho (los constructores de `catphan_db` que ahora importa
    `tac_mensual`) y como lo muestra lo reabierto: mismos encabezados y mismo numero de filas. Las CELDAS no se comparan aqui (con las series reales difieren por
    razones que no son de este cambio: lo guardado se redondea); lo fresco contra las copias locales de `HEAD`, celda por celda, lo comprueba `gi3_pantallas_frescas.py`."""
    for categoria, constructor in (("valores_ct", C.tabla_resultados_ct), ("uniformidad", C.tabla_resultados_uniformidad),
                                   ("resolucion_espacial", C.tabla_resultados_resolucion_espacial), ("resolucion_contraste", C.tabla_resultados_resolucion_contraste)):
        fresco = constructor(base_real.salidas[categoria])
        reabierto = constructor(_reabrir(base_real.ruta, categoria, base_real.sesion))
        tabla_f = fresco if isinstance(fresco, QTableWidget) else fresco.findChild(QTableWidget)
        tabla_r = reabierto if isinstance(reabierto, QTableWidget) else reabierto.findChild(QTableWidget)
        assert (tabla_f is None) == (tabla_r is None), categoria
        if tabla_f is None:
            continue
        assert _encabezados(tabla_f) == _encabezados(tabla_r), categoria
        assert len(_celdas(tabla_f)) == len(_celdas(tabla_r)), categoria


def test_tac_mensual_no_define_ninguna_copia_de_los_constructores_de_pantalla():
    """UNA sola definicion de lo que se ve de cada prueba: los seis constructores son los de `catphan_db`, importados; el modulo de `tac_mensual` ya no los define."""
    arbol = ast.parse(TAC_MENSUAL.read_text(encoding="utf-8"))
    definidas = {n.name for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name.startswith("tabla_resultados_")}
    assert definidas == {"tabla_resultados_linealidad"}, f"copias locales de los constructores: {sorted(definidas)}"
    importadas = {a.name for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("catphan_db") for a in n.names}
    esperadas = {"tabla_resultados_espesor", "tabla_resultados_tamano_pixel", "tabla_resultados_resolucion_contraste", "tabla_resultados_resolucion_espacial",
                 "tabla_resultados_ct", "tabla_resultados_uniformidad"}
    assert esperadas <= importadas
    import ui.paginasControles.PruebasMensuales.tac_mensual as tac
    for nombre in esperadas:
        assert getattr(tac, nombre) is getattr(C, nombre), nombre


def test_el_texto_de_linealidad_de_un_analisis_recien_hecho_no_lanza_con_nada(app):
    from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
    metodo = PruebaMensualTAC.tabla_resultados_linealidad
    completo = {"pendiente": 1.5, "intercepto": -3.25, "r_squared": 0.99912345, "referencia": 0.5, "escala_contraste": 0.000123456789}
    assert "HU = 1.5000 * (μ) + -3.2500" in metodo(None, completo) and "(R²): 0.9991" in metodo(None, completo)
    for hostil in HOSTILES:
        for clave in completo:
            texto = metodo(None, dict(completo, **{clave: hostil}))
            assert "None" not in texto
    assert metodo(None, {}) == "No hay resultados de linealidad disponibles." and "N/A" in metodo(None, {"pendiente": 1.0})


def test_las_pantallas_de_un_analisis_recien_hecho_formatean_los_escalares_de_numpy(app):
    """El analisis entrega `numpy.float32`/`int64`, que no son instancias de `float` ni de `int`: la tabla de un analisis recien hecho (los mismos
    constructores que lo reabierto) los formatea igual que a los numeros que lee la base, no los toma por «no disponible»."""
    import numpy as np
    uniformidad = {"Centro": {"promedio_hu": np.float32(12.34), "desviacion": np.float32(2.5)}}
    celdas = _celdas(C.tabla_resultados_uniformidad(uniformidad))
    assert celdas[0][:3] == ["Centro", "12.3", "2.5"], celdas
    ct = C.tabla_resultados_ct([{"material": "Aire", "promedio_hu": np.float32(-990.04), "rango_hu": [-1060, -940], "error_abs": np.float32(10.0), "error_rel": "Dentro de rango"}])
    assert _celdas(ct)[0][:2] == ["Aire", "-990.0"]
    assert C._es_numero(np.float32(1.5)) and C._es_numero(np.int64(3)) and not C._es_numero(np.bool_(True)) and not C._es_numero(True) and not C._es_numero("1")


@pytest.mark.parametrize("valor, formato, esperado", [
    (3, "{:.2f}", "3.00"), (2.5, "{:.1f}", "2.5"), (0, "{:.2f}", "0.00"), (-1, "{:.2f}", "-1.00"), (6, None, "6"),
    (None, "{:.2f}", "N/A"), ("No disponible", "{:.2f}", "N/A"), ("", "{:.2f}", "N/A"), (b"\x01", "{:.2f}", "N/A"), (True, "{:.2f}", "N/A"),
    (float("inf"), "{:.2f}", "N/A"), (float("-inf"), None, "N/A"), (float("nan"), "{:.2f}", "N/A"), (10 ** 400, "{:.2f}", "N/A"),     # no son medidas
])
def test_las_celdas_numericas_del_pdf_dicen_el_numero_o_n_a(valor, formato, esperado):
    from models.PDF.Imagenes.reportes_control_sistema_imagenes import _celda_numero
    assert _celda_numero(valor, formato) == esperado


def test_las_celdas_numericas_del_pdf_aceptan_los_escalares_de_numpy_y_los_veredictos_se_dicen_en_palabras():
    import numpy as np
    from models.PDF.Imagenes.reportes_control_sistema_imagenes import _celda_numero, _celda_texto, _celda_valor, _celda_veredicto
    assert _celda_numero(np.float32(2.5), "{:.2f}") == "2.50" and _celda_numero(np.int64(7)) == "7"
    assert [_celda_veredicto(v) for v in (True, 1, False, 0, None)] == ["Sí", "Sí", "No", "No", "N/A"]
    # un veredicto guardado como BLOB (los controles de antes de GI.1) o como texto se lee por lo que DICE, no por su veracidad: bool(b'\x00') y bool('No') son True
    assert [_celda_veredicto(v) for v in (b"\x00", b"\x01", b"", bytearray(b"\x00"), "No", "no", "Sí", "si", "0", "1", "false", "texto raro", "")] == \
        ["No", "Sí", "N/A", "No", "No", "No", "Sí", "Sí", "No", "Sí", "No", "N/A", "N/A"]
    assert [_celda_texto(v) for v in (None, "", "  ", "OK", 3)] == ["N/A", "N/A", "N/A", "OK", "3"]
    assert [_celda_valor(v, "{:.1f}") for v in (None, 2.04, "Fuera de Rango", True)] == ["N/A", "2.0", "Fuera de Rango", "True"]


# ---------------------------------------------------------------------------
# 6. UN FALLO DE PANTALLA SE DICE (la deuda de GI.2: la excepcion de UN constructor vaciaba la reapertura con `label`)
# ---------------------------------------------------------------------------

@pytest.fixture
def sesion_completa(bd_nueva, monkeypatch):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"espesor": _resultado_espesor(2.5), "resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6), (15, 9)),
                             "valores_ct": _materiales_ct(False), "uniformidad": _resultado_uniformidad(True, True)}, espesor_corte=2.0) == sesion
    _con_la_base(bd_nueva, monkeypatch)
    yield sesion
    _cerrar_la_base()


def _etiqueta():
    padre = QWidget()
    etiqueta = QLabel("antes", padre)
    etiqueta._padre = padre
    return etiqueta


def test_un_constructor_que_lanza_se_dice_en_la_pestana_y_los_datos_se_devuelven(sesion_completa, monkeypatch, capsys):
    def roto(resultados):
        raise ValueError("boom de prueba")
    monkeypatch.setattr(C, "tabla_resultados_resolucion_contraste", roto)
    etiqueta = _etiqueta()
    todo = C.reconstruir_resultados_desde_bd(sesion_completa, categorias=["resolucion_contraste"], label=etiqueta)
    assert "resolucion_contraste" in todo and todo["resolucion_contraste"]["resumen"]["rois_visibles_visibilidad"] == 5, "los datos que el lector leyo no se pierden"
    assert "No se pudo mostrar esta prueba guardada (resolucion_contraste)" in etiqueta.text() and "boom de prueba" in etiqueta.text()
    assert "Los datos siguen guardados" in etiqueta.text() and etiqueta.text() != "antes"
    assert "Traceback" in capsys.readouterr().err


def test_un_constructor_que_lanza_no_vacia_las_demas_categorias(sesion_completa, monkeypatch):
    monkeypatch.setattr(C, "tabla_resultados_resolucion_contraste", lambda r: 1 / 0)
    todo = C.reconstruir_resultados_desde_bd(sesion_completa, label=_etiqueta())
    assert sorted(todo) == ["espesor", "resolucion_contraste", "uniformidad", "valores_ct"], sorted(todo)


def test_la_colocacion_del_contenido_que_lanza_tambien_se_dice(sesion_completa, monkeypatch):
    monkeypatch.setattr(C, "crear_widget_con_parametros_imagen_y_contenido", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no se pudo colocar")))
    etiqueta = _etiqueta()
    todo = C.reconstruir_resultados_desde_bd(sesion_completa, categorias=["uniformidad"], label=etiqueta)
    assert "uniformidad" in todo and "no se pudo colocar" in etiqueta.text()


def test_con_label_un_lector_que_lanza_se_dice_y_sigue_con_las_demas(sesion_completa, monkeypatch):
    monkeypatch.setattr(C, "reconstruir_resolucion_contraste", lambda *a: (_ for _ in ()).throw(KeyError("columna")))
    etiqueta = _etiqueta()
    todo = C.reconstruir_resultados_desde_bd(sesion_completa, label=etiqueta)
    assert sorted(todo) == ["espesor", "uniformidad", "valores_ct"], sorted(todo)
    chica = _etiqueta()
    assert C.reconstruir_resultados_desde_bd(sesion_completa, categorias=["resolucion_contraste"], label=chica) == {}
    assert "No se pudo mostrar esta prueba guardada (resolucion_contraste)" in chica.text() and "columna" in chica.text()


def test_con_label_un_fallo_de_la_base_tambien_se_dice_en_la_pestana(sesion_completa, monkeypatch, capsys):
    """El ultimo camino mudo: la base misma falla (no una prueba): con `label` la pestana lo dice y la reapertura devuelve `{}`; sin `label`, `{}` como siempre."""
    def sin_base():
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(C.Conexion, "conectar", lambda self: sin_base())
    etiqueta = _etiqueta()
    assert C.reconstruir_resultados_desde_bd(sesion_completa, categorias=["uniformidad"], label=etiqueta) == {}
    assert "No se pudo mostrar esta prueba guardada (uniformidad)" in etiqueta.text() and "database is locked" in etiqueta.text()
    assert "Los datos siguen guardados" not in etiqueta.text(), "si falla la base no se sabe si los datos siguen guardados: no se promete"
    assert "Traceback" in capsys.readouterr().err
    assert C.reconstruir_resultados_desde_bd(sesion_completa, categorias=["uniformidad"]) == {}


def test_sin_label_un_lector_que_lanza_hace_fallar_la_reapertura_entera_como_siempre(sesion_completa, monkeypatch):
    """El PDF (mensual y anual) no tiene donde decir un fallo por categoria y un informe firmado sin una prueba en silencio seria peor que uno que no sale: la
    reapertura entera devuelve `{}` y el informe avisa «No se pudieron reconstruir los resultados»."""
    monkeypatch.setattr(C, "reconstruir_resolucion_contraste", lambda *a: (_ for _ in ()).throw(KeyError("columna")))
    assert C.reconstruir_resultados_desde_bd(sesion_completa) == {}


def test_un_widget_que_ya_no_existe_no_convierte_el_aviso_en_otro_fallo(sesion_completa, monkeypatch):
    class Muerto:
        def parent(self):
            return object()

        def setText(self, texto):
            raise RuntimeError("wrapped C/C++ object of type QLabel has been deleted")
    monkeypatch.setattr(C, "tabla_resultados_uniformidad", lambda r: 1 / 0)
    todo = C.reconstruir_resultados_desde_bd(sesion_completa, categorias=["uniformidad"], label=Muerto())
    assert "uniformidad" in todo


def test_sin_label_no_se_construye_ninguna_pantalla_aunque_fuera_a_lanzar(sesion_completa, monkeypatch):
    for nombre in CONSTRUCTORES_PANTALLA.values():
        monkeypatch.setattr(C, nombre, lambda r: 1 / 0)
    assert sorted(C.reconstruir_resultados_desde_bd(sesion_completa)) == ["espesor", "resolucion_contraste", "uniformidad", "valores_ct"]


def test_una_prueba_registrada_sin_su_fila_de_resultados_no_deja_la_pestana_muda(sesion_completa, bd_nueva):
    """Una prueba vigente sin su fila hija (un guardado parcial): el lector da None, el constructor dice «No hay resultados» y la reapertura no lanza."""
    _ejecutar(bd_nueva, "DELETE FROM resolucion_contraste")
    etiqueta = _etiqueta()
    todo = C.reconstruir_resultados_desde_bd(sesion_completa, categorias=["resolucion_contraste"], label=etiqueta)
    assert todo == {} and etiqueta.text() != "antes"


# ---------------------------------------------------------------------------
# 7. TRIPWIRES POR AST
# ---------------------------------------------------------------------------

def test_el_modulo_del_pdf_no_escribe_marcas_de_correcto_ni_incorrecto():
    """DA-18: ninguna cadena del modulo del PDF de imagenes lleva una marca de correcto/incorrecto/advertencia (se dice «Si», «No», «N/A»)."""
    arbol = ast.parse(PDF_IMAGENES.read_text(encoding="utf-8"))
    cadenas = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert len(cadenas) > 100, "el censo no examino el modulo"
    simbolos = set("✓✔✗✘❌✅⚠")
    malas = [c for c in cadenas if simbolos & set(c)]
    assert not malas, malas


def test_los_tres_constructores_del_pdf_no_leen_las_claves_de_antes():
    funciones = _funciones(PDF_IMAGENES)
    for nombre, prohibidas in (("_crear_tabla_uniformidad", {"hu_promedio"}),
                               ("_crear_tabla_resolucion_contraste", {"rois_visibles_visibilidad_lim", "pasa_test_visibilidad_lim"}),
                               ("_crear_tabla_resolucion_espacial", {"lp/mm", "lp_mm_maximo"})):
        cadenas = {n.value for n in ast.walk(funciones[nombre]) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        assert len(cadenas) > 8, nombre
        assert not cadenas & prohibidas, (nombre, sorted(cadenas & prohibidas))
