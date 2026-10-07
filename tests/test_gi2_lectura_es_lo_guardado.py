"""GI.2 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, H5, H6, D3 y D4): lo que se lee al reabrir es lo que se guardo.

CAUSA (medida el 06-10 sobre las copias de las BD de referencia y con el analisis real de las tres series): los siete lectores `reconstruir_*`
de `catphan_db.py` no devolvian lo que el analisis midio y la base guardo. El tamano de pixel devolvia `"Y": x` (la Y de la pantalla y del PDF era
la X: distintas en el Halcyon real, 0.982 y 0.963) y no leia `error_pct`; la linealidad leia la bandera guardada como BLOB con `bool(b'\\x00')`,
que es True aunque el BLOB sea un cero; los Valores CT de un control sin imagen perdian el septimo material porque la tabla quitaba SIEMPRE el
ultimo elemento (que solo es un diccionario de metadatos cuando hay imagen); la uniformidad entregaba las regiones con los nombres del catalogo
("Superior"/"Inferior") y no con los del analisis ("Arriba"/"Abajo"), y un 'No disponible' guardado en un ROI hacia reventar la tabla y, con ella,
la reapertura ENTERA (`reconstruir_resultados_desde_bd` devolvia `{}` para todas las categorias, tambien para el PDF); el espesor reabierto
inventaba los cuatro espesores por rampa (el promedio repetido) y tres renglones fijos; la resolucion espacial devolvia `'lp/mm'` por region
(el analisis da `'lp/cm'`: la region N vale N lp/cm) y su pantalla rotulaba lp/mm y no mostraba nada de lo guardado desde 05/2026; y el resumen
de contraste de los controles guardados con el defecto de GI.1 (05/2026 a 09/2026) seguia NULL/0 aunque su detalle por ROI esta completo.

GARANTIAS, una por bloque:

  1. IDA Y VUELTA CON EL ANALISIS REAL -- el analisis REAL de una serie por equipo, guardado con el escritor real en una BD nueva y leido con los
     lectores reales, devuelve campo a campo lo que el analisis midio (lo guardado, con los nombres del analisis); un lector no inventa nada.
  2. UNA CATEGORIA POR LECTOR, con la forma del productor (sin corpus) -- tamano de pixel con X distinta de Y y su `error_pct`; la bandera de
     linealidad en BLOB `\\x00` y `\\x01`; los siete materiales con y sin imagen; la uniformidad con ROI en texto; el espesor reabierto sin lo
     inventado; el contraste con el resumen NULL (conteo y veredicto derivados del detalle, con la frontera del minimo); la resolucion espacial de
     un control nuevo, de uno de enero a abril (lp/mm) y de uno guardado con el defecto de GI.1 (NULL).
  3. LAS PANTALLAS DE LO GUARDADO -- la tabla de resolucion espacial rotula y lee lp/cm; la de Valores CT muestra los siete materiales con y sin
     imagen; la de uniformidad no revienta con texto y dice "No disponible"; la de espesor solo dice lo guardado.
  4. LA REAPERTURA ENTERA -- un ROI en texto ya no tumba las demas categorias.
  5. LO QUE EL PDF TODAVIA LEE (transicion hasta GI.3) -- el PDF es de GI.3: sus constructores siguen leyendo `'lp/mm'` por region y `*_lim` del
     resumen de contraste; hasta GI.3 el lector los entrega con el valor que tenian (compuerta de cero diferencias del PDF).
  6. TRIPWIRES por AST -- los lectores no nombran lo que no esta guardado; ningun recorte ciego del ultimo elemento.

FRONTERA con GI.3 (lo que esta prueba NO cambia a proposito): los rotulos y los constructores del PDF y la tabla de «Ver tabla»; la maxima
resolucion y la MTF de los controles de enero a abril siguen en la unidad con la que se guardaron (el PDF los rotula todavia 'lp/mm', y alli son
lp/mm): el lector deduce la unidad de la fila (`unidad_guardada`) para que GI.3 las convierta al mismo tiempo que cambia el rotulo.

Nunca se conecta a una BD de referencia: las bases son nuevas o copias en un temporal.
"""
import ast
import os
import pathlib
import shutil
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QTableWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.catphan_TAC import catphan_db as C
from data.ManejoDatos.conection import Conexion
from _bd_referencia import BD_REBUILD_21_09
from test_gi1_guardado_claves_del_analisis import (  # noqa: F401  (helpers y fixtures de GI.1: una sola definicion de la forma del productor)
    ID_TIPO, _crear_control, _forma_linealidad, _guardar, _id_prueba, _leer, _region, _resultado_contraste, _resultado_espesor,
    _resultado_uniformidad, app, bd_nueva, base_real)

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CATPHAN_DB = RAIZ / "data" / "ManejoDatos" / "catphan_TAC" / "catphan_db.py"


# ---------------------------------------------------------------------------
# Ayudas
# ---------------------------------------------------------------------------

def _con_la_base(ruta, monkeypatch):
    """La base `ruta` como la base de la aplicacion (con sus migraciones al abrir): para llamar a las funciones que abren `Conexion()`."""
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    Conexion()


def _cerrar_la_base():
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = None


def _reabrir(ruta, categoria, sesion):
    """Lo que devuelve el lector de `categoria` sobre lo guardado en `sesion`: el lector real, sobre un cursor de sqlite3 y con la imagen que la
    prueba guardo (`pruebas.imagen_resultado`), como lo llama `reconstruir_resultados_desde_bd`."""
    con = _leer(ruta)
    try:
        id_prueba = _id_prueba(con, sesion, categoria)
        imagen = con.execute("SELECT imagen_resultado FROM pruebas WHERE id_prueba = ?", (id_prueba,)).fetchone()[0]
        lector = getattr(C, "reconstruir_" + {"espesor": "espesor_corte", "uniformidad": "uniformidad"}.get(categoria, categoria))
        return lector(con.cursor(), id_prueba, imagen)
    finally:
        con.close()


def _ejecutar(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        con.execute(sql, parametros)
        con.commit()
    finally:
        con.close()


def _pantalla_sin_ventana():
    """Los constructores de tabla crean `QTableWidget`: basta con la `QApplication` del fixture `app`."""


def _celdas(tabla):
    """Texto de cada celda de un `QTableWidget` (lista de filas)."""
    return [[(tabla.item(f, c).text() if tabla.item(f, c) is not None else None) for c in range(tabla.columnCount())]
            for f in range(tabla.rowCount())]


def _encabezados(tabla):
    return [tabla.horizontalHeaderItem(c).text() for c in range(tabla.columnCount())]


# Las marcas que el PDF (de GI.3) imprime hoy; con escapes para no escribir los simbolos que DA-18 prohibe en textos nuevos. Aqui se fija lo que HEAD imprime.
VISTO, CRUZ = "\u2713", "\u2717"


# ---------------------------------------------------------------------------
# 1. IDA Y VUELTA CON EL ANALISIS REAL (una serie por equipo)
# ---------------------------------------------------------------------------

def _reabierto(base_real, categoria):
    return _reabrir(base_real.ruta, categoria, base_real.sesion)


def test_real_el_espesor_reabierto_es_lo_guardado_y_no_inventa_nada(base_real):
    """Las claves de lo reabierto son EXACTAMENTE las que se guardaron: promedio, teorico, diferencia y error; los cuatro espesores por rampa, el
    factor de correccion, las rampas detectadas y la combinacion de cortes no se guardan y no se inventan."""
    espesor = base_real.salidas["espesor"]
    r = _reabierto(base_real, "espesor")
    assert set(r) == {"espesor_promedio_mm", "espesor_teorico_mm", "diferencia_mm", "error_pct", "imagen_analisis"}, sorted(r)
    assert r["espesor_promedio_mm"] == round(espesor["espesor_promedio_mm"], 3)
    assert r["espesor_teorico_mm"] == round(base_real.nominal, 3)
    assert r["diferencia_mm"] == round(abs(espesor["espesor_promedio_mm"] - base_real.nominal), 3)
    assert r["error_pct"] == pytest.approx(abs(espesor["espesor_promedio_mm"] - base_real.nominal) / base_real.nominal * 100, abs=1e-3)


def test_real_el_tamano_de_pixel_reabierto_trae_x_y_y_por_separado_y_el_error(base_real):
    salida = base_real.salidas["tamano_pixel"]
    r = _reabierto(base_real, "tamano_pixel")
    assert r["X"] == salida["X"] and r["Y"] == salida["Y"], (r["X"], r["Y"], salida["X"], salida["Y"])
    assert r["tam_px_teorico"] == pytest.approx(base_real.px, abs=5e-4), "el escritor guarda el teorico redondeado a tres decimales"
    assert r["diferencia_x"] == pytest.approx(abs(salida["X"] - base_real.px), abs=1e-3)
    assert r["diferencia_y"] == pytest.approx(abs(salida["Y"] - base_real.px), abs=1e-3)
    media = (salida["X"] + salida["Y"]) / 2
    assert r["error_pct"] == pytest.approx(abs(round(base_real.px, 3) - round(media, 3)) / round(base_real.px, 3) * 100, abs=1e-3)


def test_real_el_resumen_de_contraste_reabierto_es_el_del_analisis(base_real):
    analisis = base_real.salidas["resolucion_contraste"]
    r = _reabierto(base_real, "resolucion_contraste")
    resumen = r["resumen"]
    for clave in ("rois_visibles_cnr", "rois_visibles_visibilidad", "total_rois"):
        assert resumen[clave] == analisis["resumen"][clave], clave
    assert bool(resumen["pasa_test_cnr"]) is bool(analisis["resumen"]["pasa_test_cnr"])
    assert bool(resumen["pasa_test_visibilidad"]) is bool(analisis["resumen"]["pasa_test_visibilidad"])
    assert set(r["resultados_roi"]) == set(analisis["resultados_roi"])
    for nombre, roi in analisis["resultados_roi"].items():
        guardado = r["resultados_roi"][nombre]
        for clave in ("roi_prom", "background_prom", "contraste_michelson", "cnr", "snr", "visibilidad_lim"):
            assert guardado[clave] == roi[clave], (nombre, clave)
        assert bool(guardado["pasa_visibilidad_lim"]) is bool(roi["pasa_visibilidad_lim"]) and bool(guardado["pasa_cnr"]) is bool(roi["pasa_cnr"])


def test_real_la_resolucion_espacial_reabierta_trae_lp_cm_por_region(base_real):
    analisis = base_real.salidas["resolucion_espacial"]
    r = _reabierto(base_real, "resolucion_espacial")
    assert set(r["region_results"]) == set(analisis["region_results"])
    for nombre, region in analisis["region_results"].items():
        guardada = r["region_results"][nombre]
        assert "lp/cm" in guardada, f"{nombre}: la region reabierta no trae la clave del analisis 'lp/cm'"
        assert guardada["lp/cm"] == region.get("lp/cm", float(nombre.split()[-1])), nombre
        assert guardada["status"] == region["status"]
        for clave in ("n_peaks_used", "n_valleys_used"):
            assert guardada[clave] == region.get(clave), (nombre, clave)
    limite = analisis["resolucion_limite"]
    assert r["resolucion_limite"]["lp_cm_maximo"] == limite["lp_cm_maximo"] and r["resolucion_limite"]["ultima_region"] == limite["ultima_region"]
    assert r["unidad_guardada"] == "lp/cm", "un control guardado hoy esta en lp/cm"
    guardadas = {k: v for k, v in analisis["mtf_lp_cm"].items() if k in ("10", "20", "50")}      # el mapeador guarda solo el 10, el 20 y el 50 %
    assert r["mtf_lp_cm"] == {k: pytest.approx(v) for k, v in guardadas.items()}


def test_real_los_valores_ct_reabiertos_traen_los_siete_materiales_con_las_cuatro_claves(base_real):
    analisis = [r for r in base_real.salidas["valores_ct"] if "material" in r]
    r = _reabierto(base_real, "valores_ct")
    materiales = [x for x in r if "material" in x]
    assert sorted(m["material"] for m in materiales) == sorted(a["material"] for a in analisis) and len(materiales) == 7
    por_nombre = {m["material"]: m for m in materiales}
    for a in analisis:
        m = por_nombre[a["material"]]
        assert m["promedio_hu"] == a["promedio_hu"] and m["error_abs"] == a["error_abs"] and m["error_rel"] == a["error_rel"], a["material"]
        assert set(m) >= {"material", "promedio_hu", "error_abs", "error_rel"}


def test_real_la_linealidad_reabierta_es_la_del_analisis(base_real):
    analisis = base_real.salidas["linealidad_ct"]
    r = _reabierto(base_real, "linealidad_ct")
    for clave in ("pendiente", "intercepto", "referencia", "escala_contraste", "energia_mev"):
        assert r[clave] == analisis[clave], clave
    assert r["r_squared"] == analisis["r_squared"]
    assert r["linealidad_aceptable"] is bool(analisis["r_squared"] >= 0.99)


def test_real_la_uniformidad_reabierta_trae_los_cinco_roi_con_los_nombres_del_analisis(base_real):
    analisis = base_real.salidas["uniformidad"]
    r = _reabierto(base_real, "uniformidad")
    nombres = {"Centro", "Arriba", "Derecha", "Abajo", "Izquierda"}
    assert set(r) == nombres | {"Uniformidad"}, sorted(r)
    for nombre in nombres:
        assert r[nombre]["promedio_hu"] == analisis[nombre]["promedio_hu"], nombre
        assert r[nombre]["desviacion"] == analisis[nombre]["desviacion"], nombre
    for clave in ("max_diferencia", "desviacion_global", "uniformity_index_max", "uniformity_index_roi", "integral_non_uniformity",
                  "integral_non_uniformity_pct"):
        assert r["Uniformidad"][clave] == analisis["Uniformidad"][clave], clave


def test_real_reabrir_la_sesion_completa_trae_las_siete_categorias(base_real, monkeypatch):
    _con_la_base(base_real.ruta, monkeypatch)
    try:
        todo = C.reconstruir_resultados_desde_bd(base_real.sesion)
    finally:
        _cerrar_la_base()
    assert sorted(todo) == sorted(ID_TIPO)


# ---------------------------------------------------------------------------
# 2. UNA CATEGORIA POR LECTOR, con la forma del productor (sin corpus)
# ---------------------------------------------------------------------------

# --- tamano de pixel ---

def test_el_tamano_de_pixel_reabierto_no_confunde_la_y_con_la_x(bd_nueva):
    """Rojo: `reconstruir_tamano_pixel` pone `"Y": x`. El Halcyon real mide X = 0.982 y Y = 0.963 (sesion 34 de la copia del 21-09)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"tamano_pixel": {"X": 0.982, "Y": 0.963, "imagen_analisis": None}}, tam_px_teorico=0.959) == sesion
    r = _reabrir(bd_nueva, "tamano_pixel", sesion)
    assert (r["X"], r["Y"]) == (0.982, 0.963)
    assert r["tam_px_teorico"] == 0.959 and r["diferencia_x"] == 0.023 and r["diferencia_y"] == 0.004
    assert r["error_pct"] == 1.356, "el error porcentual guardado se lee (la pantalla ya lo pide con `.get('error_pct')`)"


def test_el_tamano_de_pixel_de_una_base_sin_la_columna_error_pct_se_lee_igual(bd_nueva):
    """`error_pct` se lee `si la columna existe`: una base que nunca la tuvo (antes de DP-41) no tumba la reapertura; el lector no inventa el dato."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"tamano_pixel": {"X": 1.0, "Y": 1.2, "imagen_analisis": None}}, tam_px_teorico=1.074) == sesion
    con = sqlite3.connect(bd_nueva)
    try:
        con.execute('ALTER TABLE "tamaño_pixel" DROP COLUMN error_pct')
        con.commit()
    except sqlite3.OperationalError:
        pytest.skip("este SQLite no soporta DROP COLUMN")
    finally:
        con.close()
    r = _reabrir(bd_nueva, "tamano_pixel", sesion)
    assert (r["X"], r["Y"]) == (1.0, 1.2) and "error_pct" not in r


# --- linealidad ---

@pytest.mark.parametrize("blob, esperado", [(b"\x00", False), (b"\x01", True)])
def test_la_bandera_de_linealidad_guardada_como_blob_se_lee_por_su_valor(bd_nueva, blob, esperado):
    """Rojo para `b'\\x00'`: `bool(b'\\x00')` es True (los BLOB guardados con `numpy.bool_`, antes de GI.1, son este caso: las cinco filas reales
    son `\\x01`, un `\\x00` es la linealidad de un control con r < 0.99). Sin reescribir la fila: se decodifica al mostrarla."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"linealidad_ct": _forma_linealidad(0.5)}) == sesion
    _ejecutar(bd_nueva, "UPDATE linealidad_ct SET linealidad_aceptable = ?", (sqlite3.Binary(blob),))
    assert _leer(bd_nueva).execute("SELECT typeof(linealidad_aceptable) FROM linealidad_ct").fetchone()[0] == "blob"
    r = _reabrir(bd_nueva, "linealidad_ct", sesion)
    assert r["linealidad_aceptable"] is esperado


@pytest.mark.parametrize("entero, esperado", [(0, False), (1, True)])
def test_la_bandera_de_linealidad_guardada_como_entero_sigue_igual(bd_nueva, entero, esperado):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"linealidad_ct": _forma_linealidad(0.5)}) == sesion
    _ejecutar(bd_nueva, "UPDATE linealidad_ct SET linealidad_aceptable = ?", (entero,))
    assert _reabrir(bd_nueva, "linealidad_ct", sesion)["linealidad_aceptable"] is esperado


def test_la_bandera_de_linealidad_sin_valor_es_none(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"linealidad_ct": _forma_linealidad(0.5)}) == sesion
    _ejecutar(bd_nueva, "UPDATE linealidad_ct SET linealidad_aceptable = NULL")
    assert _reabrir(bd_nueva, "linealidad_ct", sesion)["linealidad_aceptable"] is None


# --- valores CT ---

def _materiales_ct(con_imagen):
    """Forma de `valor_numero_ct`: siete materiales y, con `visualizar`, un ultimo elemento solo con la imagen."""
    nombres = ("Teflon", "Delrin", "Acrilico", "Poliestireno", "LDPE", "PMP", "Aire")
    lista = [{"centro": (10 * n, 20 * n), "material": m, "promedio_hu": 100.0 * n - 300, "std_hu": 1.5, "rango_hu": (0, 1),
              "error_abs": 0.0 if n % 2 else 12.5, "error_rel": "Dentro del Rango" if n % 2 else "Fuera de Rango"}
             for n, m in enumerate(nombres, start=1)]
    if con_imagen:
        lista.append({"imagen_analisis": b"\x89PNG\r\n\x1a\nimagen"})
    return lista


def _guardar_valores_ct(ruta, con_imagen):
    """Los siete materiales guardados con el escritor real y, si `con_imagen`, la imagen del analisis en `pruebas.imagen_resultado` (la que guarda
    `guardar_prueba_completa_catphan` cuando recibe el corte DICOM y el `output_blob`; aqui se escribe directo)."""
    sesion = _crear_control(ruta)
    assert _guardar(sesion, {"valores_ct": _materiales_ct(con_imagen)}) == sesion
    if con_imagen:
        _ejecutar(ruta, "UPDATE pruebas SET imagen_resultado = ? WHERE id_tipo = 5", (sqlite3.Binary(b"\x89PNG\r\n\x1a\nimagen"),))
    return sesion


@pytest.mark.parametrize("con_imagen", [True, False])
def test_los_valores_ct_reabiertos_traen_los_siete_materiales_con_y_sin_imagen(bd_nueva, con_imagen):
    sesion = _guardar_valores_ct(bd_nueva, con_imagen)
    r = _reabrir(bd_nueva, "valores_ct", sesion)
    materiales = [x for x in r if "material" in x]
    assert len(materiales) == 7
    assert {m["material"] for m in materiales} == {"Aire", "PMP", "LDPE", "Poliestireno", "Acrilico", "Delrin", "Teflon"}
    for m in materiales:
        assert set(m) == {"material", "promedio_hu", "error_abs", "error_rel", "rango_hu"}, "las cuatro claves que el escritor lee (GI.1) se conservan"
    # con imagen el ultimo elemento es el diccionario de metadatos; sin imagen NO hay elemento de metadatos
    assert len(r) == (8 if con_imagen else 7)
    assert ("_metadata" in r[-1]) is con_imagen


@pytest.mark.parametrize("con_imagen", [True, False])
def test_la_tabla_de_valores_ct_muestra_los_siete_materiales_con_y_sin_imagen(app, bd_nueva, con_imagen):
    """Rojo sin imagen: `tabla_resultados_ct` quitaba SIEMPRE el ultimo elemento (el septimo material si no habia metadatos): las sesiones 21 y 47."""
    sesion = _guardar_valores_ct(bd_nueva, con_imagen)
    tabla = C.tabla_resultados_ct(_reabrir(bd_nueva, "valores_ct", sesion))
    assert isinstance(tabla, QTableWidget) and tabla.rowCount() == 7
    filas = _celdas(tabla)
    assert all(f[0] and f[1] for f in filas), filas
    assert {f[0] for f in filas} == {"Aire", "PMP", "LDPE", "Poliestireno", "Acrílico", "Delrin", "Teflón"}


def test_la_tabla_de_valores_ct_con_la_forma_del_analisis_fresco_sigue_quitando_los_metadatos(app):
    """Control (lo que NO cambia): el analisis fresco entrega siete materiales y un ultimo elemento `{'imagen_analisis': ...}` (sin `'material'`
    ni `'_metadata'`); la tabla muestra los siete y ninguna fila de metadatos."""
    tabla = C.tabla_resultados_ct(_materiales_ct(True))
    assert tabla.rowCount() == 7 and len(_celdas(tabla)) == 7
    assert all(f[0] and f[0] != "None" for f in _celdas(tabla))


def test_la_tabla_de_valores_ct_con_un_elemento_de_metadatos_en_la_forma_del_lector(app):
    """El elemento de metadatos de lo reabierto es `{'_metadata': {...}}`: tampoco es una fila."""
    lista = [x for x in _materiales_ct(False)] + [{"_metadata": {"imagen_analisis": b"x"}}]
    assert C.tabla_resultados_ct(lista).rowCount() == 7


def test_la_tabla_de_valores_ct_acepta_el_diccionario_con_resultados(app):
    """Compatibilidad hacia atras de la funcion: `{'resultados': [...]}` tambien se muestra completo."""
    assert C.tabla_resultados_ct({"resultados": _materiales_ct(False)}).rowCount() == 7
    assert C.tabla_resultados_ct({"resultados": _materiales_ct(True)}).rowCount() == 7


# --- uniformidad ---

def test_la_uniformidad_reabierta_usa_los_nombres_del_analisis(bd_nueva):
    """Rojo: el catalogo siembra 'Superior'/'Inferior' y el analisis, el escritor y `criterios.unif_max_dif_hu` dicen 'Arriba'/'Abajo'."""
    from analisisImagenes.catphan.criterios import ruido_centro_hu, unif_max_dif_hu
    resultado = _resultado_uniformidad(True, False)
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": resultado}) == sesion
    r = _reabrir(bd_nueva, "uniformidad", sesion)
    assert set(r) == {"Centro", "Arriba", "Derecha", "Abajo", "Izquierda", "Uniformidad"}
    for nombre in ("Centro", "Arriba", "Derecha", "Abajo", "Izquierda"):
        assert r[nombre] == {"promedio_hu": resultado[nombre]["promedio_hu"], "desviacion": resultado[nombre]["desviacion"]}
    assert unif_max_dif_hu(r) == unif_max_dif_hu(resultado) is not None, "criterios.unif_max_dif_hu juzga lo reabierto como lo fresco"
    assert ruido_centro_hu(r) == ruido_centro_hu(resultado)


def test_un_roi_de_uniformidad_guardado_como_texto_se_lee_sin_reventar(bd_nueva):
    """El escritor guarda 'No disponible' en `uniformidad_ruido.hu_promedio` (REAL NOT NULL: no puede ser NULL) cuando el analisis no trajo el
    dato. Reabrir devuelve None para ese valor (el dato que el analisis tenia) y `criterios` lo ignora; el resto del ROI sigue igual."""
    from analisisImagenes.catphan.criterios import unif_max_dif_hu
    resultado = _resultado_uniformidad(True, True)
    resultado["Derecha"]["promedio_hu"] = None
    resultado["Derecha"]["desviacion"] = None
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": resultado}) == sesion
    tipos = _leer(bd_nueva).execute("SELECT typeof(hu_promedio), typeof(desviacion) FROM uniformidad_ruido WHERE hu_promedio = 'No disponible'").fetchall()
    assert [tuple(t) for t in tipos] == [("text", "text")], "el escritor guarda el texto (los NOT NULL no admiten NULL)"
    r = _reabrir(bd_nueva, "uniformidad", sesion)
    assert r["Derecha"] == {"promedio_hu": None, "desviacion": None}
    assert r["Arriba"]["promedio_hu"] == resultado["Arriba"]["promedio_hu"]
    assert unif_max_dif_hu(r) is not None


def test_la_tabla_de_uniformidad_dice_no_disponible_en_vez_de_reventar(app, bd_nueva):
    """Rojo: `round('No disponible', 1)` lanzaba TypeError. Un ROI sin dato sigue siendo una fila de la tabla y dice que no hay dato."""
    resultado = _resultado_uniformidad(True, True)
    resultado["Derecha"]["promedio_hu"] = None
    resultado["Derecha"]["desviacion"] = None
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": resultado}) == sesion
    tabla = C.tabla_resultados_uniformidad(_reabrir(bd_nueva, "uniformidad", sesion))
    filas = _celdas(tabla)
    posiciones = {f[0]: f[1:] for f in filas if f[0] in ("Centro", "Arriba", "Derecha", "Abajo", "Izquierda")}
    assert set(posiciones) == {"Centro", "Arriba", "Derecha", "Abajo", "Izquierda"}, f"faltan filas: {filas}"
    assert posiciones["Derecha"] == ["No disponible", "No disponible"]
    assert posiciones["Arriba"] == [str(round(resultado["Arriba"]["promedio_hu"], 1)), str(round(resultado["Arriba"]["desviacion"], 1))]


# --- espesor ---

def test_el_espesor_reabierto_no_inventa_los_cuatro_por_rampa_ni_los_renglones_fijos(app, bd_nueva):
    """Rojo: el lector devolvia el promedio repetido como 'espesores individuales' y `factor_correccion = 0.42`, `num_rampas_detectadas = 4`,
    `combinacion_slices = False`, que no se guardan. Lo reabierto es lo guardado (D4)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"espesor": _resultado_espesor(2.5)}, espesor_corte=2.0) == sesion
    r = _reabrir(bd_nueva, "espesor", sesion)
    assert r["espesor_promedio_mm"] == 2.5 and r["espesor_teorico_mm"] == 2.0 and r["diferencia_mm"] == 0.5 and r["error_pct"] == 25.0
    for inventada in ("espesores_individuales", "factor_correccion", "num_rampas_detectadas", "combinacion_slices"):
        assert inventada not in r, f"el lector inventa '{inventada}'"
    texto = C.tabla_resultados_espesor(r)
    assert "Espesor promedio: 2.5 mm" in texto and "Espesor teórico: 2.0 mm" in texto and "Diferencia: 0.5 mm" in texto
    for inventada in ("Factor corrección", "Rampas detectadas", "Combinación slices", "Espesores individuales", "Izquierda", "Arriba"):
        assert inventada not in texto, f"la pantalla de lo guardado dice '{inventada}', que no se guardo"


def test_la_tabla_de_espesor_de_un_analisis_fresco_sigue_mostrando_lo_que_trae(app):
    """Control (lo que NO cambia): un diccionario con las claves del analisis (si alguien llama a la funcion con lo fresco) imprime sus renglones."""
    fresco = {"espesor_promedio_mm": 2.1, "espesor_teorico_mm": 2.0, "diferencia_mm": 0.1, "factor_correccion": 0.42,
              "num_rampas_detectadas": 4, "combinacion_slices": True,
              "espesores_individuales": {"Izquierda": 2.0, "Abajo": 2.1, "Derecha": 2.2, "Arriba": 2.1}}
    texto = C.tabla_resultados_espesor(fresco)
    for esperado in ("Factor corrección: 0.42", "Rampas detectadas: 4", "Combinación slices: Sí", "Izquierda: 2.0 mm", "Arriba: 2.1 mm"):
        assert esperado in texto, esperado


# --- contraste ---

def _forzar_resumen_de_contraste_nulo(ruta, **valores):
    """Un control guardado con el defecto de GI.1 (05/2026 a 09/2026): `rois_visibles_visibilidad` NULL y `pasa_test_visibilidad` = 0 (`bool(None)`)."""
    _ejecutar(ruta, "UPDATE resolucion_contraste SET rois_visibles_visibilidad = NULL, pasa_test_visibilidad = 0")
    for columna, valor in valores.items():
        _ejecutar(ruta, f"UPDATE resolucion_contraste SET {columna} = ?", (valor,))


@pytest.mark.parametrize("visibles, esperado_pasa", [
    ((15, 9, 8), False),                         # 3 de 6: no pasa
    ((15, 9, 8, 7), True),                       # EXACTAMENTE el minimo (4): pasa (la frontera)
    ((15, 9, 8, 7, 6, 5), True),                 # 6 de 6: pasa (la sesion 48 real: guardo 'no pasa' con 6/6 visibles)
    ((), False),                                 # ninguna: 0, no None
])
def test_el_resumen_de_contraste_nulo_se_deriva_del_detalle_por_roi(bd_nueva, visibles, esperado_pasa):
    """Rojo: con el resumen NULL el lector devolvia None y 0 aunque el detalle por ROI esta completo. Conteo y veredicto se derivan al mostrar,
    con el minimo del analisis (`criterios.PARAMETROS_HEREDADOS`): una sola fuente."""
    from analisisImagenes.catphan.criterios import PARAMETROS_HEREDADOS
    minimo = PARAMETROS_HEREDADOS["resolucion_contraste"]["min_rois_visibles"]
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste(visibles, (15, 9))}) == sesion
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] == len(visibles)
    assert r["pasa_test_visibilidad"] is (len(visibles) >= minimo) is esperado_pasa
    assert r["rois_visibles_cnr"] == 2 and r["total_rois"] == 6, "lo que SI estaba guardado no se toca"


def test_el_minimo_de_roi_visibles_de_la_derivacion_es_el_de_la_fuente_unica(bd_nueva, monkeypatch):
    """El veredicto derivado usa `criterios.PARAMETROS_HEREDADOS` (el mismo minimo que el analisis), no un 4 escrito en el lector: si la fuente
    cambia, el veredicto derivado la sigue."""
    from analisisImagenes.catphan import criterios
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9), (15, 9))}) == sesion
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    assert _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]["pasa_test_visibilidad"] is False       # 2 < 4
    monkeypatch.setitem(criterios.PARAMETROS_HEREDADOS["resolucion_contraste"], "min_rois_visibles", 2)
    assert _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]["pasa_test_visibilidad"] is True        # 2 >= 2


def test_el_resumen_de_contraste_guardado_no_se_deriva_ni_se_pisa(bd_nueva):
    """Control: con el conteo guardado (controles de enero a abril y los guardados desde GI.1) el lector devuelve lo guardado, aunque el detalle
    contara otra cosa (la fila guarda lo que el analisis dijo)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7), (15, 9, 8, 7))}) == sesion
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste SET rois_visibles_visibilidad = 5, pasa_test_visibilidad = 0")
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] == 5 and bool(r["pasa_test_visibilidad"]) is False


def test_un_resumen_nulo_sin_detalle_por_roi_no_inventa_un_conteo(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9), (15, 9))}) == sesion
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    _ejecutar(bd_nueva, "DELETE FROM resolucion_contraste_rois")
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] is None
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste SET total_rois = NULL")      # ni el detalle ni el total guardado: sin nada que contar no se inventa un 0 (C1)
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] is None and r["total_rois"] is None and r["pasa_test_visibilidad"] is False


# --- resolucion espacial ---

def _guardar_espacial_antiguo(ruta, sesion, ultima, lp_maximo, regiones_lp, mtf):
    """Un control guardado como los de enero a abril de 2026 (la frecuencia en lp/mm: la region N guardo N/10) o con el defecto de GI.1 (NULL).
    Se reescribe lo que el escritor dejo, con los valores del dato real (`regiones_lp`: {region: lp guardado o None})."""
    _ejecutar(ruta, "UPDATE resolucion_espacial SET lp_cm_maximo = ?, ultima_region_exitosa = ?, mtf_10_pct = ?, mtf_20_pct = ?, mtf_50_pct = ?",
              (lp_maximo, ultima, *mtf))
    for region, lp in regiones_lp.items():
        _ejecutar(ruta, "UPDATE resolucion_espacial_regiones SET lp_cm = ? WHERE region_nombre = ?", (lp, region))


def _espacial_de_ocho_regiones():
    """Las tres primeras regiones OK con todos sus datos; las cinco restantes solo con su estado y su frecuencia nominal, como las que el analisis
    real no logra medir. Los `lp/cm` son `float` como los de la base."""
    regiones = {f"region {n}": dict(_region(n, "OK"), **{"lp/cm": float(n)}) if n <= 3
                else {"lp/cm": float(n), "status": "Picos insuficientes"} for n in range(1, 9)}
    return {"region_results": regiones, "mtf_values": {}, "mtf_lp_cm": {"50": 2.6}, "num_picos": 9, "valores_picos": [],
            "resolucion_limite": {"ultima_region": "region 3", "lp_cm_maximo": 3, "gap_size_cm": 0.167}, "imagen_analisis": None}


def test_un_control_nuevo_reabre_lp_cm_por_region_con_la_clave_del_analisis(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert {n: reg["lp/cm"] for n, reg in r["region_results"].items()} == {f"region {n}": float(n) for n in range(1, 9)}
    assert r["unidad_guardada"] == "lp/cm"
    assert r["resolucion_limite"]["lp_cm_maximo"] == 3 and r["mtf_lp_cm"] == {"50": 2.6}


def test_un_control_de_enero_a_abril_reabre_en_lp_cm_desde_el_nombre_de_la_region(bd_nueva):
    """Rojo: la region 3 de un control de enero a abril guardo 0.3 (lp/mm): reabierto debe decir 3.0 lp/cm. La unidad de la fila se deduce de sus
    propias regiones (0.3 = 3 / 10), y la maxima y la MTF NO se convierten todavia (GI.3 las rotula)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _guardar_espacial_antiguo(bd_nueva, sesion, "region 3", 0.3, {f"region {n}": n / 10 for n in range(1, 9)}, (None, None, 0.2628))
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert {n: reg["lp/cm"] for n, reg in r["region_results"].items()} == {f"region {n}": float(n) for n in range(1, 9)}
    assert r["unidad_guardada"] == "lp/mm"
    assert r["resolucion_limite"]["lp_cm_maximo"] == 0.3 and r["mtf_lp_cm"] == {"50": 0.2628}, "la maxima y la MTF siguen como se guardaron"


def test_un_control_guardado_con_el_defecto_de_gi1_reabre_lp_cm_desde_el_nombre_de_la_region(bd_nueva):
    """Rojo: los controles de 05/2026 a 09/2026 dejaron `lp_cm` NULL en las ocho regiones y su maxima en lp/cm (7, 3, 4...). La region N vale N lp/cm."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _guardar_espacial_antiguo(bd_nueva, sesion, "region 3", 3.0, {f"region {n}": None for n in range(1, 9)}, (None, 2.87, 2.17))
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert {n: reg["lp/cm"] for n, reg in r["region_results"].items()} == {f"region {n}": float(n) for n in range(1, 9)}
    assert r["unidad_guardada"] == "lp/cm", "sin lp por region la unidad sale de la maxima (3.0) contra la ultima region (region 3)"
    assert r["resolucion_limite"]["lp_cm_maximo"] == 3.0 and r["mtf_lp_cm"] == {"20": 2.87, "50": 2.17}


@pytest.mark.parametrize("regiones_lp, maximo, ultima, esperada", [
    ({"region 1": 0.1, "region 2": 0.2}, 0.2, "region 2", "lp/mm"),             # enero a abril
    ({"region 1": 1.0, "region 2": 2.0}, 2.0, "region 2", "lp/cm"),              # control nuevo
    ({"region 1": None, "region 2": None}, 0.2, "region 2", "lp/mm"),            # sin regiones: la maxima contra la ultima region
    ({"region 1": None, "region 2": None}, 2.0, "region 2", "lp/cm"),
    ({"region 1": None, "region 2": None}, -1, None, "lp/cm"),                   # el centinela: ninguna region OK -> la convencion actual
    ({"region 1": None, "region 2": None}, None, None, "lp/cm"),                 # nada que deducir: la convencion actual
    ({"region 3": 0.3, "region 4": 0.4}, 0.4, "region 4", "lp/mm"),
    ({"region 1": 0.1}, None, None, "lp/mm"),                                    # solo las regiones deciden (sin resumen)
    ({"region 1": 1.0}, None, None, "lp/cm"),
    ({"region 1": None, "region 2": 0.2}, None, None, "lp/mm"),                  # una region con valor basta
    ({"region 1": 0.1, "region 2": None}, 2.0, "region 2", "lp/mm"),             # las regiones mandan sobre el resumen
])
def test_la_unidad_de_la_fila_se_deduce_de_sus_propios_valores(regiones_lp, maximo, ultima, esperada):
    assert C.unidad_de_la_fila_espacial(list(regiones_lp.items()), maximo, ultima) == esperada


def test_una_region_con_un_lp_cm_guardado_que_no_es_ni_n_ni_n_sobre_10_se_respeta():
    """El lector solo deriva lo que FALTA (NULL) o lo que esta en la unidad vieja reconocible (N/10): un lp_cm guardado distinto se muestra tal cual."""
    assert C._lp_cm_de_la_region("region 3", 6.0) == 6.0
    assert C._lp_cm_de_la_region("region 3", 3.0) == 3.0 and C._lp_cm_de_la_region("region 3", 0.3) == 3.0 and C._lp_cm_de_la_region("region 3", None) == 3.0
    assert C._lp_cm_de_la_region("region 7", 0.7) == 7.0
    assert C._lp_cm_de_la_region("sin numero", None) is None and C._lp_cm_de_la_region("sin numero", 2.5) == 2.5


def test_las_regiones_reabiertas_van_en_orden_de_region_aunque_el_lp_guardado_sea_null(bd_nueva):
    """El lector ordenaba por la columna `lp_cm`: con las ocho NULL el orden era el que SQLite quisiera. Ahora es el de region 1..8."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _ejecutar(bd_nueva, "UPDATE resolucion_espacial_regiones SET lp_cm = NULL")
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert list(r["region_results"]) == [f"region {n}" for n in range(1, 9)]


def test_las_regiones_reabiertas_van_en_orden_de_region_aunque_se_hayan_guardado_desordenadas(bd_nueva):
    """El orden es el de region 1..8 y no el de las filas: con los `id` invertidos (guardadas de la 8 a la 1) la tabla sigue en orden."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _ejecutar(bd_nueva, "UPDATE resolucion_espacial_regiones SET id = 1000 - id")
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert list(r["region_results"]) == [f"region {n}" for n in range(1, 9)]


# ---------------------------------------------------------------------------
# 3. LAS PANTALLAS DE LO GUARDADO
# ---------------------------------------------------------------------------

def test_la_tabla_de_resolucion_espacial_rotula_lp_cm_y_muestra_lo_guardado(app, bd_nueva):
    """Rojo: encabezado 'lp/mm' y lectura de `'lp/mm'` (con GI.1 mostraba 1.0, 2.0, 3.0 bajo 'lp/mm' y, al renombrar la clave del lector, quedaria
    VACIA para todo control)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    tabla = C.tabla_resultados_resolucion_espacial(_reabrir(bd_nueva, "resolucion_espacial", sesion))
    assert _encabezados(tabla) == ["Región", "lp/cm", "N° Picos", "N° Valles", "Gap Size (cm)"]
    filas = _celdas(tabla)
    assert [f[:2] for f in filas] == [["Región 1", "1.0"], ["Región 2", "2.0"], ["Región 3", "3.0"]], filas


@pytest.mark.parametrize("como", ["enero_a_abril", "defecto_de_gi1"])
def test_la_tabla_de_resolucion_espacial_de_un_control_viejo_muestra_las_regiones_en_lp_cm(app, bd_nueva, como):
    """Los de enero a abril (0.1, 0.2, 0.3 lp/mm) y los de 05/2026 a 09/2026 (NULL) se ven en lp/cm: 1, 2, 3 (la region N)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    if como == "enero_a_abril":
        _guardar_espacial_antiguo(bd_nueva, sesion, "region 3", 0.3, {f"region {n}": n / 10 for n in range(1, 9)}, (None, None, 0.26))
    else:
        _guardar_espacial_antiguo(bd_nueva, sesion, "region 3", 3.0, {f"region {n}": None for n in range(1, 9)}, (None, None, 2.6))
    tabla = C.tabla_resultados_resolucion_espacial(_reabrir(bd_nueva, "resolucion_espacial", sesion))
    assert [f[:2] for f in _celdas(tabla)] == [["Región 1", "1.0"], ["Región 2", "2.0"], ["Región 3", "3.0"]]
    assert _encabezados(tabla)[1] == "lp/cm"


def test_la_tabla_de_resolucion_espacial_del_analisis_fresco_se_lee_igual(app):
    """Control: la misma funcion con un diccionario del analisis (solo `'lp/cm'`, nunca `'lp/mm'`) muestra los mismos numeros."""
    r = _espacial_de_ocho_regiones()
    tabla = C.tabla_resultados_resolucion_espacial(r)
    assert [f[:2] for f in _celdas(tabla)] == [["Región 1", "1.0"], ["Región 2", "2.0"], ["Región 3", "3.0"]]


# ---------------------------------------------------------------------------
# 4. LA REAPERTURA ENTERA
# ---------------------------------------------------------------------------

def test_un_roi_en_texto_ya_no_tumba_la_reapertura_de_las_demas_categorias(app, bd_nueva, monkeypatch):
    """Rojo: `tabla_resultados_uniformidad` lanzaba TypeError con el texto y el `except` externo de `reconstruir_resultados_desde_bd` devolvia
    `{}`: las siete categorias se perdian (tambien para el PDF, que llama a la misma funcion con `label=None`)."""
    uniformidad = _resultado_uniformidad(True, True)
    uniformidad["Abajo"]["promedio_hu"] = None
    uniformidad["Abajo"]["desviacion"] = None
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": uniformidad, "valores_ct": _materiales_ct(False), "tamano_pixel": {"X": 1.0, "Y": 1.1, "imagen_analisis": None},
                             "espesor": _resultado_espesor(2.0)}, espesor_corte=2.0) == sesion
    _con_la_base(bd_nueva, monkeypatch)
    try:
        todo = C.reconstruir_resultados_desde_bd(sesion)
    finally:
        _cerrar_la_base()
    assert sorted(todo) == ["espesor", "tamano_pixel", "uniformidad", "valores_ct"], sorted(todo)
    assert todo["uniformidad"]["Abajo"] == {"promedio_hu": None, "desviacion": None}
    assert len([x for x in todo["valores_ct"] if "material" in x]) == 7


# ---------------------------------------------------------------------------
# 5. LO QUE EL PDF TODAVIA LEE (transicion hasta GI.3)
# ---------------------------------------------------------------------------

def _pdf():
    from models.PDF.Imagenes.reportes_control_sistema_imagenes import ReporteControlSistemaImagenes
    return object.__new__(ReporteControlSistemaImagenes)


def _filas_pdf(tabla):
    return [list(f) for f in tabla.values.tolist()]


def test_transicion_el_pdf_sigue_leyendo_lp_mm_por_region_con_lo_guardado(bd_nueva):
    """El PDF (GI.3) lee `'lp/mm'` por region: hasta GI.3 el lector entrega ahi lo que se guardo (0.1, 0.2... en enero a abril; None si NULL), asi
    la tabla impresa de un control reabierto es la de hoy. GI.3 cambia el constructor del PDF a `'lp/cm'` y RETIRA este shim y esta prueba."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _guardar_espacial_antiguo(bd_nueva, sesion, "region 3", 0.3, {f"region {n}": n / 10 for n in range(1, 9)}, (None, None, 0.26))
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert {n: reg["lp/mm"] for n, reg in r["region_results"].items()} == {f"region {n}": n / 10 for n in range(1, 9)}
    filas = _filas_pdf(_pdf()._crear_tabla_resolucion_espacial(r))
    assert [f[:2] for f in filas[1:4]] == [["region 1", "0.10"], ["region 2", "0.20"], ["region 3", "0.30"]]
    resumen = {f[0]: f[1] for f in filas}
    assert resumen["Resolución máxima"] == "0.30" and resumen["MTF 50%"] == "0.26"


def test_transicion_el_pdf_sigue_leyendo_los_asteriscos_lim_del_resumen_de_contraste(bd_nueva):
    """El PDF lee `rois_visibles_visibilidad_lim` y `pasa_test_visibilidad_lim` del resumen: hasta GI.3 el lector los entrega con lo guardado
    (None / 0 en los controles con el defecto de GI.1) y ademas las claves del analisis (derivadas). GI.3 retira las `*_lim` y esta prueba."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6, 5), (15, 9))}) == sesion
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    resumen = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert resumen["rois_visibles_visibilidad"] == 6 and resumen["pasa_test_visibilidad"] is True            # derivado
    assert resumen["rois_visibles_visibilidad_lim"] is None and not resumen["pasa_test_visibilidad_lim"]   # lo guardado, como hoy


def test_transicion_el_pdf_de_tamano_de_pixel_imprime_la_y_guardada(bd_nueva):
    """Lo NOMBRADO que cambia en el PDF: 'Y medido' imprime la Y guardada, no la X."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"tamano_pixel": {"X": 0.982, "Y": 0.963, "imagen_analisis": None}}, tam_px_teorico=0.959) == sesion
    filas = {f[0]: f[1] for f in _filas_pdf(_pdf()._crear_tabla_tamano_pixel(_reabrir(bd_nueva, "tamano_pixel", sesion)))}
    assert filas["X medido"] == "0.982 mm" and filas["Y medido"] == "0.963 mm"


def test_transicion_el_pdf_de_uniformidad_ya_encuentra_los_cinco_roi_por_nombre(bd_nueva):
    """El PDF itera ['Centro', 'Arriba', 'Derecha', 'Abajo', 'Izquierda']: con los nombres del analisis en lo reabierto las dos filas que faltaban
    ('Arriba' y 'Abajo', guardadas como 'Superior'/'Inferior') aparecen. Su HU lo arregla GI.3 (el PDF lee `hu_promedio`, el analisis dice `promedio_hu`)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": _resultado_uniformidad(True, True)}) == sesion
    filas = _filas_pdf(_pdf()._crear_tabla_uniformidad(_reabrir(bd_nueva, "uniformidad", sesion)))
    regiones = [f[0] for f in filas[1:6]]
    assert regiones == ["Centro", "Arriba", "Derecha", "Abajo", "Izquierda"]


# --- la compuerta «el PDF no cambia entre GI.2 y GI.3», afirmada sobre lo que el PDF IMPRIME en cada uno de los casos reales (lente reproducir, GI2-R2) ---
# Son los casos que ya estan en las BD: resumen de contraste guardado (enero a abril y desde GI.1) o NULL (05/2026 a 09/2026), y la frecuencia por region en
# lp/cm (control nuevo), en lp/mm (enero a abril) o NULL (05/2026 a 09/2026). Los valores esperados son los que el PDF imprime con el lector de HEAD
# (cada caso pasa tambien contra el `catphan_db.py` de HEAD: es un control de que GI.2 no cambia lo impreso).

@pytest.mark.parametrize("resumen_nulo, visibles, fila_esperada", [
    (False, (15, 9, 8, 7, 6), ["5", VISTO]),                  # guardado: 5 visibles y pasa
    (False, (15, 9, 8), ["3", CRUZ]),                         # guardado: 3 visibles y no pasa
    (True, (15, 9, 8, 7, 6, 5), ["None", CRUZ]),              # NULL (defecto de GI.1): el PDF no ve el conteo DERIVADO (6 y pasa) hasta GI.3
])
def test_el_pdf_de_contraste_imprime_en_cada_caso_lo_que_imprime_hoy(bd_nueva, resumen_nulo, visibles, fila_esperada):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste(visibles, (15, 9))}) == sesion
    if resumen_nulo:
        _forzar_resumen_de_contraste_nulo(bd_nueva)
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)
    filas = {f[0]: f[1:] for f in _filas_pdf(_pdf()._crear_tabla_resolucion_contraste(r))}
    assert filas["ROIs visibles"] == fila_esperada
    assert filas["Diámetro mínimo visible (mm)"] == ["N/A", CRUZ]


@pytest.mark.parametrize("como, lp_por_region, maximo, mtf, regiones_esperadas, maxima_esperada, mtf50_esperada", [
    ("nuevo", None, None, None, [["region 1", "1.00"], ["region 2", "2.00"], ["region 3", "3.00"]], "3.00", "2.60"),
    ("enero a abril", {f"region {n}": n / 10 for n in range(1, 9)}, 0.3, (None, None, 0.2628),
     [["region 1", "0.10"], ["region 2", "0.20"], ["region 3", "0.30"]], "0.30", "0.26"),
    ("defecto de GI.1", {f"region {n}": None for n in range(1, 9)}, 3.0, (None, 2.87, 2.17),
     [["region 1", "None"], ["region 2", "None"], ["region 3", "None"]], "3.00", "2.17"),
])
def test_el_pdf_de_resolucion_espacial_imprime_en_cada_caso_lo_que_imprime_hoy(bd_nueva, como, lp_por_region, maximo, mtf, regiones_esperadas,
                                                                              maxima_esperada, mtf50_esperada):
    """El PDF rotula 'lp/mm' y GI.3 lo pasa a lp/cm: hasta entonces imprime lo GUARDADO crudo (1.00 de un control nuevo, 0.10 de uno de enero a abril, None de uno
    con el defecto de GI.1), la maxima y la MTF como se guardaron; nunca el lp/cm derivado del nombre de la region (que el lector entrega aparte)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    if lp_por_region is not None:
        _guardar_espacial_antiguo(bd_nueva, sesion, "region 3", maximo, lp_por_region, mtf)
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    filas = _filas_pdf(_pdf()._crear_tabla_resolucion_espacial(r))
    assert [f[:2] for f in filas[1:4]] == regiones_esperadas, como
    por_nombre = {f[0]: f for f in filas}
    assert por_nombre["Resolución máxima"][1] == maxima_esperada and por_nombre["MTF 50%"][1] == mtf50_esperada, como


# ---------------------------------------------------------------------------
# 6. TRIPWIRES POR AST
# ---------------------------------------------------------------------------

def _funciones(archivo):
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)}


LECTORES = ("reconstruir_espesor_corte", "reconstruir_tamano_pixel", "reconstruir_resolucion_contraste", "reconstruir_resolucion_espacial",
            "reconstruir_valores_ct", "reconstruir_linealidad_ct", "reconstruir_uniformidad")


def test_el_lector_de_espesor_no_nombra_lo_que_no_se_guarda():
    """Lo que el escritor NO guarda no se inventa al leer: ninguna cadena del lector de espesor es una de esas claves."""
    funcion = _funciones(CATPHAN_DB)["reconstruir_espesor_corte"]
    cadenas = {n.value for n in ast.walk(funcion) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert {"espesor_promedio_mm", "error_pct"} <= cadenas, "el censo no examino el lector de espesor (no vio lo que SI entrega)"
    inventadas = cadenas & {"espesores_individuales", "factor_correccion", "num_rampas_detectadas", "combinacion_slices",
                            "Izquierda", "Abajo", "Derecha", "Arriba"}
    assert not inventadas, f"el lector inventa lo que no se guarda: {sorted(inventadas)}"
    constantes = [n.value for n in ast.walk(funcion) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    assert 0.42 not in constantes


def _recortes_ciegos(funcion):
    """Lineas de `funcion` (un `ast.FunctionDef`) donde se quita el ultimo elemento sin mirar que es: `x[:-1]` y `len(x) - 1`."""
    ciegos = []
    for nodo in ast.walk(funcion):
        if isinstance(nodo, ast.Subscript) and isinstance(nodo.slice, ast.Slice) and nodo.slice.lower is None:
            sup = nodo.slice.upper
            if isinstance(sup, ast.UnaryOp) and isinstance(sup.op, ast.USub) and isinstance(sup.operand, ast.Constant) and sup.operand.value == 1:
                ciegos.append(nodo.lineno)
        if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Sub) and isinstance(nodo.right, ast.Constant) and nodo.right.value == 1 \
                and isinstance(nodo.left, ast.Call) and getattr(nodo.left.func, "id", "") == "len":
            ciegos.append(nodo.lineno)
    return ciegos


def test_el_detector_de_recortes_ciegos_los_ve():
    """El censo de abajo no es vacuo: sobre codigo con `x[:-1]` y con `len(x) - 1` el detector da una linea por recorte, y sobre codigo sin ellos, ninguna."""
    con = ast.parse("def f(r):\n    a = r[:-1]\n    for i in range(len(r) - 1):\n        pass\n").body[0]
    sin = ast.parse("def f(r):\n    return [x for x in r if 'material' in x]\n").body[0]
    assert _recortes_ciegos(con) == [2, 3] and _recortes_ciegos(sin) == []


def test_la_tabla_de_valores_ct_no_recorta_el_ultimo_elemento_a_ciegas():
    """`resultados[:-1]` y `len(resultados) - 1` quitaban un elemento que solo es metadatos CUANDO HAY IMAGEN."""
    funcion = _funciones(CATPHAN_DB)["tabla_resultados_ct"]
    assert any(isinstance(n, ast.Subscript) for n in ast.walk(funcion)), "el censo no examino el cuerpo de tabla_resultados_ct"
    ciegos = _recortes_ciegos(funcion)
    assert not ciegos, f"tabla_resultados_ct recorta el ultimo elemento sin comprobar que es metadatos (lineas {ciegos})"


def test_la_tabla_de_resolucion_espacial_de_catphan_db_no_lee_ni_rotula_lp_mm():
    """El rotulo y la lectura de la pantalla de lo guardado son lp/cm (D3)."""
    funcion = _funciones(CATPHAN_DB)["tabla_resultados_resolucion_espacial"]
    cadenas = [n.value for n in ast.walk(funcion) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not [c for c in cadenas if "lp/mm" in c], [c for c in cadenas if "lp/mm" in c]
    assert any(c == "lp/cm" for c in cadenas)


# ---------------------------------------------------------------------------
# 7. LA COMPUERTA SOBRE LAS SESIONES REALES (copia de Rebuild_21-09)
# ---------------------------------------------------------------------------

@pytest.fixture
def bd_copia_real(monkeypatch, tmp_path, app):
    if not BD_REBUILD_21_09.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_21_09.name}")
    copia = tmp_path / "copia.db"
    shutil.copy2(BD_REBUILD_21_09, copia)
    _con_la_base(str(copia), monkeypatch)
    yield str(copia)
    _cerrar_la_base()


SESIONES_REALES = (6, 8, 12, 21, 25, 30, 34, 42, 47, 48)


def test_las_diez_sesiones_reales_reabren_completas(bd_copia_real):
    """Sobre la copia de la BD del 21-09: todas las categorias guardadas de las diez sesiones se reabren, sin que ninguna tumbe a las demas (los NOMBRES de
    las categorias; el VALOR de cada una contra SQL directo lo comprueba `test_cada_sesion_real_reabre_con_lo_que_su_tabla_guardo`)."""
    con = _leer(bd_copia_real)
    try:
        esperado = {s: sorted({ID_TIPO_INVERSO[r[0]] for r in con.execute(
            "SELECT id_tipo FROM pruebas WHERE id_sesion = ? AND (activo IS NULL OR activo = 1)", (s,))}) for s in SESIONES_REALES}
    finally:
        con.close()
    for sesion in SESIONES_REALES:
        todo = C.reconstruir_resultados_desde_bd(sesion)
        assert sorted(todo) == esperado[sesion], (sesion, sorted(todo), esperado[sesion])


ID_TIPO_INVERSO = {v: k for k, v in ID_TIPO.items()}


def test_las_sesiones_reales_con_siete_materiales_sin_imagen_los_muestran_todos(bd_copia_real):
    """Las sesiones 21 y 47 (Valores CT sin imagen guardada): la tabla muestra los siete materiales."""
    for sesion in (21, 47):
        todo = C.reconstruir_resultados_desde_bd(sesion, categorias=["valores_ct"])
        materiales = [x for x in todo["valores_ct"] if "material" in x]
        assert len(materiales) == 7, (sesion, len(materiales))
        assert C.tabla_resultados_ct(todo["valores_ct"]).rowCount() == 7, sesion


def test_la_sesion_34_real_reabre_con_la_y_del_halcyon(bd_copia_real):
    """La sesion 34 (Halcyon, 06/2026): X = 0.982 y Y = 0.963 en la base; el lector decia Y = 0.982."""
    r = C.reconstruir_resultados_desde_bd(34, categorias=["tamano_pixel"])["tamano_pixel"]
    assert (r["X"], r["Y"]) == (0.982, 0.963)


def test_la_sesion_48_real_reabre_con_el_conteo_y_el_veredicto_del_detalle(bd_copia_real):
    """La sesion 48: 'no pasa' guardado con 6/6 ROI visibles en su detalle; reabierta dice 6 y pasa (el detalle por ROI es lo guardado)."""
    r = C.reconstruir_resultados_desde_bd(48, categorias=["resolucion_contraste"])["resolucion_contraste"]["resumen"]
    assert r["rois_visibles_visibilidad"] == 6 and r["pasa_test_visibilidad"] is True


# ---------------------------------------------------------------------------
# 8. ENDURECIMIENTO: las mutaciones que la primera version de esta prueba dejaba sobrevivir
#    (las propuso la lente "reproducir" de la revision escéptica sobre una copia: formato de los numeros, la bandera en BLOB vacio, el numero de region,
#    las tolerancias de la unidad, la unidad deducida de las regiones o del resumen, lo que el PDF todavia lee, el tipo de los veredictos, el resaltado)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valor, decimales, esperado", [
    (-391.567, 1, "-391.6"), (12.3456, 2, "12.35"), (12.0, 1, "12.0"), (0.0, 1, "0.0"), (0, 1, "0"), (7, 1, "7"),
    ("No disponible", 1, "No disponible"), (None, 1, "No disponible"), (True, 1, "No disponible"), ("1.5", 1, "No disponible")])
def test_el_texto_de_un_numero_redondea_a_los_decimales_pedidos_y_dice_cuando_no_hay_dato(valor, decimales, esperado):
    assert C._texto_de_numero(valor, decimales) == esperado
    assert C.CENTINELA_NO_DISPONIBLE == "No disponible"


@pytest.mark.parametrize("valor, esperado", [
    (0, True), (0.0, True), (-1.5, True), (3, True), (2.5, True), (True, False), (False, False), ("1", False), ("No disponible", False),
    (None, False), (b"\x01", False)])
def test_un_numero_es_un_numero_y_un_booleano_no_lo_es(valor, esperado):
    assert C._es_numero(valor) is esperado


@pytest.mark.parametrize("valor, esperado", [(0, 0), (0.0, 0.0), (-1.5, -1.5), (7, 7), ("No disponible", None), (None, None), (True, None), (b"\x01", None)])
def test_solo_un_numero_guardado_pasa_y_un_cero_legitimo_se_conserva(valor, esperado):
    resultado = C._numero_o_none(valor)
    assert resultado == esperado and type(resultado) is type(esperado)


@pytest.mark.parametrize("valor, esperado", [
    (None, None), (b"", None), (bytearray(), None),                                    # nada que decodificar: no se inventa ni True ni False
    (b"\x00", False), (b"\x01", True), (b"\x00\x00", False), (b"\x01\x00", True), (b"\x00\x01", True), (b"\xff", True),
    (bytearray(b"\x00"), False), (bytearray(b"\x01"), True), (memoryview(b"\x00"), False), (memoryview(b"\x01"), True),
    (0, False), (1, True), (2, True), (0.0, False)])
def test_la_bandera_guardada_se_decodifica_por_su_valor(valor, esperado):
    assert C._bandera_guardada(valor) is esperado


@pytest.mark.parametrize("nombre, esperado", [
    ("region 3", 3), ("region 10", 10), ("region 12", 12), ("region 3   ", 3), ("Región 7", 7), ("7", 7), ("2 regiones: region 5", 5), ("a1 b2", 2),
    ("sin numero", None), ("", None), (None, None), ("region 3 (2 picos)", None), ("region", None)])
def test_el_numero_de_la_region_es_el_que_termina_el_nombre(nombre, esperado):
    assert C._numero_de_region(nombre) == esperado


@pytest.mark.parametrize("valor, n, esperado", [
    (0.3, 3, True), (0.7, 7, True), (0.1, 1, True), (0.8, 8, True),                    # el ruido de coma flotante (0.7 * 10) no es un motivo para rechazar
    (0.32, 3, False), (0.35, 3, False), (3.0, 3, False), (0.0, 3, False), (-0.3, 3, False), (0.3, None, False), (0.3, 4, False), (True, 1, False),
    ("0.3", 3, False), (None, 3, False)])
def test_la_frecuencia_en_lp_mm_es_exactamente_n_sobre_10(valor, n, esperado):
    assert C._es_lp_mm(valor, n) is esperado


@pytest.mark.parametrize("valor, n, esperado", [
    (3.0, 3, True), (3, 3, True), (1.0, 1, True), (8.0, 8, True),
    (3.4, 3, False), (3.5, 3, False), (0.3, 3, False), (0.0, 3, False), (-3.0, 3, False), (3.0, None, False), (3.0, 4, False), (True, 1, False), (None, 3, False)])
def test_la_frecuencia_en_lp_cm_es_exactamente_n(valor, n, esperado):
    assert C._es_lp_cm(valor, n) is esperado


@pytest.mark.parametrize("nombre, guardado, esperado", [
    ("region 3", 3.4, 3.4), ("region 3", 0.32, 0.32), ("region 3", 6.0, 6.0),          # un lp/cm guardado utilizable que no es ni N ni N/10 se respeta
    ("region 3", 0.3, 3.0), ("region 7", 0.7, 7.0), ("region 3", None, 3.0), ("region 3", 3.0, 3.0), ("region 3", "No disponible", 3.0),
    ("sin numero", None, None), ("sin numero", 2.5, 2.5)])
def test_el_lp_cm_de_una_region_deriva_solo_lo_que_falta_o_esta_en_la_unidad_vieja(nombre, guardado, esperado):
    assert C._lp_cm_de_la_region(nombre, guardado) == esperado


@pytest.mark.parametrize("regiones, maximo, ultima, esperada", [
    ([("region 1", 0.1), ("region 2", 2.0)], None, None, "lp/mm"),                      # fila mezclada: basta una region en la unidad vieja
    ([("region 1", 1.0), ("region 2", 0.2)], None, None, "lp/mm"),
    ([("region 1", 0.1), ("region 2", 2.0)], 2.0, "region 2", "lp/mm"),
    ([("region 1", 1.0), ("region 2", 2.0)], 0.2, "region 2", "lp/cm"),                  # las regiones mandan sobre el resumen
    ([("region 1", None), ("region 2", None)], 0.3, "region 3", "lp/mm"),                # sin valores por region decide el resumen
    ([("region 1", None), ("region 2", None)], 3.0, "region 3", "lp/cm"),
    ([("region 1", None)], -1, None, "lp/cm"), ([], None, None, "lp/cm"), ([], 0.3, "region 3", "lp/mm"), ([], 3.0, "region 3", "lp/cm"),
    ([], 0.3, None, "lp/cm"), ([], None, "region 3", "lp/cm"), ([], 3.0, 3.0, "lp/cm")])
def test_la_unidad_de_la_fila_con_casos_limite(regiones, maximo, ultima, esperada):
    assert C.unidad_de_la_fila_espacial(regiones, maximo, ultima) == esperada


@pytest.mark.parametrize("regiones_lp, lp_maximo, ultima, esperada", [
    ({f"region {n}": n / 10 for n in range(1, 9)}, None, None, "lp/mm"),                # solo las regiones (el resumen no dice nada)
    ({f"region {n}": float(n) for n in range(1, 9)}, None, None, "lp/cm"),
    ({f"region {n}": None for n in range(1, 9)}, 0.3, "region 3", "lp/mm"),             # solo el resumen
    ({f"region {n}": None for n in range(1, 9)}, 3.0, "region 3", "lp/cm"),
    ({f"region {n}": None for n in range(1, 9)}, -1, None, "lp/cm"),                    # nada que deducir: la convencion de hoy
])
def test_el_lector_deduce_la_unidad_con_las_regiones_o_con_el_resumen(bd_nueva, regiones_lp, lp_maximo, ultima, esperada):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _guardar_espacial_antiguo(bd_nueva, sesion, ultima, lp_maximo, regiones_lp, (None, None, None))
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert r["unidad_guardada"] == esperada
    assert {n: reg["lp/cm"] for n, reg in r["region_results"].items()} == {f"region {n}": float(n) for n in range(1, 9)}


def test_una_region_sin_numero_en_el_nombre_va_al_final_y_conserva_su_lp_guardado(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _ejecutar(bd_nueva, "UPDATE resolucion_espacial_regiones SET region_nombre = 'sin numero', lp_cm = 2.5 WHERE region_nombre = 'region 4'")
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert list(r["region_results"]) == ["region 1", "region 2", "region 3", "region 5", "region 6", "region 7", "region 8", "sin numero"]
    assert r["region_results"]["sin numero"]["lp/cm"] == 2.5


def test_la_tabla_de_resolucion_espacial_resalta_solo_la_maxima_formatea_y_excluye_lo_no_positivo(app):
    regiones = {
        "region 1": dict(_region(1, "OK"), **{"lp/cm": 1.25}), "region 2": dict(_region(2, "OK"), **{"lp/cm": 2.5}),
        "region 3": dict(_region(3, "OK"), **{"lp/cm": 3.75}), "region 4": dict(_region(4, "OK"), **{"lp/cm": 0.0}),
        "region 5": dict(_region(5, "OK"), **{"lp/cm": -1.0})}
    tabla = C.tabla_resultados_resolucion_espacial({"region_results": regiones})
    assert [f[:2] for f in _celdas(tabla)] == [["Región 1", "1.25"], ["Región 2", "2.5"], ["Región 3", "3.75"]]
    fondos = [tabla.item(i, 0).background().color().name() for i in range(3)]
    assert fondos[2] == "#9aedc8" and fondos[0] != "#9aedc8" and fondos[1] != "#9aedc8", fondos


@pytest.mark.parametrize("faltante", ["n_peaks_used", "n_valleys_used", "gap_size_cm"])
def test_la_tabla_de_resolucion_espacial_exige_los_tres_numeros_de_una_region_medida(app, faltante):
    """N15 (lente reproducir): el filtro de «datos completos» pide picos, valles y gap numericos cada uno por su cuenta: una region a la que le falta UNO
    (aunque tenga los otros dos y su lp/cm nominal) no es una region medida y no sale en la tabla."""
    regiones = {"region 2": _region(2, "OK"), "region 3": _region(3, "OK", **{faltante: None})}
    tabla = C.tabla_resultados_resolucion_espacial({"region_results": regiones})
    assert [f[0] for f in _celdas(tabla)] == ["Región 2"], faltante


def test_con_el_resumen_de_contraste_guardado_el_pdf_ve_lo_guardado(bd_nueva):
    """Transicion: un control CON el resumen guardado (enero a abril y los guardados desde GI.1): las claves `*_lim` que el PDF todavia lee traen lo
    guardado (5 ROI visibles y el veredicto), el PDF imprime ese conteo y el veredicto impreso de 3 ROI es otro que el de 5."""
    sesion = _crear_control(bd_nueva)

    def abrir(visibles):                          # guardar otra vez la misma categoria reemplaza el bloque (la fila anterior se anula)
        assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste(visibles, (15, 9))}) == sesion
        return _reabrir(bd_nueva, "resolucion_contraste", sesion)
    cinco = abrir((15, 9, 8, 7, 6))
    resumen = cinco["resumen"]
    assert resumen["rois_visibles_visibilidad_lim"] == 5 and bool(resumen["pasa_test_visibilidad_lim"]) is True
    assert resumen["rois_visibles_visibilidad"] == 5 and resumen["pasa_test_visibilidad"] is True
    fila_cinco = {f[0]: f[1:] for f in _filas_pdf(_pdf()._crear_tabla_resolucion_contraste(cinco))}["ROIs visibles"]
    assert fila_cinco[0] == "5"
    tres = abrir((15, 9, 8))
    assert tres["resumen"]["rois_visibles_visibilidad_lim"] == 3 and bool(tres["resumen"]["pasa_test_visibilidad_lim"]) is False
    fila_tres = {f[0]: f[1:] for f in _filas_pdf(_pdf()._crear_tabla_resolucion_contraste(tres))}["ROIs visibles"]
    assert fila_tres[0] == "3" and fila_tres[1] != fila_cinco[1], "el veredicto impreso de 3 ROI debe ser otro que el de 5"


def test_los_veredictos_del_resumen_son_booleanos_y_un_null_no_se_inventa(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6), (15, 9))}) == sesion
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["pasa_test_visibilidad"] is True and r["pasa_test_cnr"] is False                 # el tipo del analisis (bool), no el 0/1 de SQLite
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste SET pasa_test_cnr = NULL, pasa_test_visibilidad = NULL")
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] == 5, "con el conteo guardado no se deriva"
    assert r["pasa_test_cnr"] is None and r["pasa_test_visibilidad"] is None, "un NULL guardado no se vuelve False"


def test_un_conteo_guardado_en_cero_es_un_valor_y_no_se_deriva(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6), (15, 9))}) == sesion
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste SET rois_visibles_visibilidad = 0, pasa_test_visibilidad = 0")
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] == 0 and r["pasa_test_visibilidad"] is False


def test_el_conteo_derivado_cuenta_solo_los_roi_visibles_y_no_los_que_pasan_cnr(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8), (7, 6, 5))}) == sesion         # 3 visibles; 3 distintos pasan CNR
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] == 3 and r["pasa_test_visibilidad"] is False
    assert r["rois_visibles_cnr"] == 3, "lo que SI estaba guardado no se toca"


def test_el_espesor_reabierto_no_redondea_el_error_porcentual_guardado(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"espesor": _resultado_espesor(2.5)}, espesor_corte=2.0) == sesion
    _ejecutar(bd_nueva, "UPDATE espesor_corte SET error_pct = 12.345")
    assert _reabrir(bd_nueva, "espesor", sesion)["error_pct"] == 12.345


def test_la_uniformidad_conserva_un_cero_guardado_y_la_tabla_lo_muestra(app, bd_nueva):
    """Un 0.0 es un valor (no 'No disponible'): el lector lo devuelve y la tabla lo dice."""
    resultado = _resultado_uniformidad(True, True)
    resultado["Derecha"]["promedio_hu"] = 0.0
    resultado["Derecha"]["desviacion"] = 0.0
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": resultado}) == sesion
    r = _reabrir(bd_nueva, "uniformidad", sesion)
    assert r["Derecha"] == {"promedio_hu": 0.0, "desviacion": 0.0}
    assert type(r["Derecha"]["promedio_hu"]) is float
    posiciones = {f[0]: f[1:] for f in _celdas(C.tabla_resultados_uniformidad(r)) if f[0] in ("Centro", "Arriba", "Derecha", "Abajo", "Izquierda")}
    assert posiciones["Derecha"] == ["0.0", "0.0"]


def test_la_tabla_de_uniformidad_redondea_a_un_decimal(app, bd_nueva):
    resultado = _resultado_uniformidad(True, True)
    resultado["Arriba"]["promedio_hu"] = -391.567
    resultado["Arriba"]["desviacion"] = 12.3456
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": resultado}) == sesion
    posiciones = {f[0]: f[1:] for f in _celdas(C.tabla_resultados_uniformidad(_reabrir(bd_nueva, "uniformidad", sesion))) if f[0] == "Arriba"}
    assert posiciones["Arriba"] == ["-391.6", "12.3"]


def test_la_tabla_de_valores_ct_muestra_un_material_sin_promedio_y_los_que_vengan(app):
    """Un material cuyo promedio no hay sigue siendo una fila (dice N/A); y una lista con mas de siete materiales los muestra todos."""
    lista = _materiales_ct(False)
    lista[2] = dict(lista[2], promedio_hu=None)
    tabla = C.tabla_resultados_ct(lista)
    assert tabla.rowCount() == 7 and _celdas(tabla)[2][1] == "N/A"
    ocho = _materiales_ct(False) + [{"material": "Otro", "promedio_hu": 5.0, "rango_hu": (0, 1), "error_abs": 0.0, "error_rel": "Dentro del Rango"}]
    tabla = C.tabla_resultados_ct(ocho)
    assert tabla.rowCount() == 8 and _celdas(tabla)[-1][0] == "Otro"


# ---------------------------------------------------------------------------
# 9. HALLAZGOS DE LA REVISION ESCEPTICA (reproducidos antes de actuar) y mutaciones de la segunda tanda del revisor "reproducir"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valor", ["No disponible", sqlite3.Binary(b"\x00")])
def test_un_error_pct_del_tamano_de_pixel_que_no_es_numero_no_tumba_la_reapertura(app, bd_nueva, monkeypatch, valor):
    """H1 (regresion de robustez, lente regresion): GI.2 empieza a LEER `tamaño_pixel.error_pct` y su tabla lo formateaba con `:.3f` sin comprobar el tipo:
    un texto o un BLOB en esa celda lanzaba TypeError y `reconstruir_resultados_desde_bd` devolvia `{}` para las siete categorias (y el PDF de imagenes decia
    «No se pudieron reconstruir los resultados»; el anual omitia la seccion en silencio). El escritor no lo produce hoy, pero es la misma clase que el
    'No disponible' de uniformidad que la tarea cierra: un valor guardado inesperado en UNA celda no vacia el resto."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"tamano_pixel": {"X": 1.0, "Y": 1.1, "imagen_analisis": None}, "espesor": _resultado_espesor(2.0)},
                    espesor_corte=2.0, tam_px_teorico=1.074) == sesion
    _ejecutar(bd_nueva, 'UPDATE "tamaño_pixel" SET error_pct = ?', (valor,))
    _con_la_base(bd_nueva, monkeypatch)
    try:
        todo = C.reconstruir_resultados_desde_bd(sesion)
    finally:
        _cerrar_la_base()
    assert sorted(todo) == ["espesor", "tamano_pixel"], f"la reapertura perdio categorias: {sorted(todo)}"
    assert "Error porcentual: " in C.tabla_resultados_tamano_pixel(todo["tamano_pixel"])


def test_la_pantalla_de_tamano_de_pixel_reabierto_dice_x_y_y_el_error_guardado(app, bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"tamano_pixel": {"X": 0.982, "Y": 0.963, "imagen_analisis": None}}, tam_px_teorico=0.959) == sesion
    texto = C.tabla_resultados_tamano_pixel(_reabrir(bd_nueva, "tamano_pixel", sesion))
    for esperado in ("X: 0.982 mm", "Y: 0.963 mm", "Teórico: 0.959 mm", "Diferencia X: 0.023 mm", "Diferencia Y: 0.004 mm", "Error porcentual: 1.356%"):
        assert esperado in texto, (esperado, texto)


def test_un_error_pct_guardado_en_cero_es_un_valor_y_se_entrega(app, bd_nueva):
    """El cero existe en datos reales (la sesion 21 midio X = Y = 0.533 = el teorico): el lector lo entrega y la pantalla lo dice."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"tamano_pixel": {"X": 1.074, "Y": 1.074, "imagen_analisis": None}}, tam_px_teorico=1.074) == sesion
    r = _reabrir(bd_nueva, "tamano_pixel", sesion)
    assert r["error_pct"] == 0.0 and type(r["error_pct"]) is float
    assert "Error porcentual: 0.000%" in C.tabla_resultados_tamano_pixel(r)


def test_la_pantalla_de_espesor_dice_los_renglones_del_analisis_aunque_valgan_cero_o_falso(app):
    """Con un diccionario del analisis (un solo corte: sin combinar; ninguna rampa; factor 0) los tres renglones se dicen: la condicion es que la CLAVE exista."""
    texto = C.tabla_resultados_espesor({"espesor_promedio_mm": 2.0, "espesor_teorico_mm": 2.0, "diferencia_mm": 0.0, "factor_correccion": 0.0,
                                        "num_rampas_detectadas": 0, "combinacion_slices": False, "espesores_individuales": {}})
    for esperado in ("Factor corrección: 0.0", "Rampas detectadas: 0", "Combinación slices: No"):
        assert esperado in texto, (esperado, texto)


def test_en_un_control_con_lp_cm_nulo_el_pdf_sigue_leyendo_none_en_lp_mm(bd_nueva):
    """Transicion, el caso NULL: la clave `'lp/mm'` que el PDF todavia lee trae lo GUARDADO crudo (None), no el lp/cm derivado: con el derivado el PDF
    imprimiria 1.00, 2.00, 3.00 bajo el rotulo 'lp/mm'. GI.3 retira la clave."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": _espacial_de_ocho_regiones()}) == sesion
    _guardar_espacial_antiguo(bd_nueva, sesion, "region 3", 3.0, {f"region {n}": None for n in range(1, 9)}, (None, None, 2.6))
    r = _reabrir(bd_nueva, "resolucion_espacial", sesion)
    assert {n: reg["lp/mm"] for n, reg in r["region_results"].items()} == {f"region {n}": None for n in range(1, 9)}
    assert {n: reg["lp/cm"] for n, reg in r["region_results"].items()} == {f"region {n}": float(n) for n in range(1, 9)}


def test_un_roi_sin_veredicto_guardado_no_cuenta_como_visible_en_la_derivacion(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7), (15, 9))}) == sesion         # 4 visibles: pasaria
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste_rois SET pasa_visibilidad_lim = NULL WHERE diametro_mm = 15")
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] == 3 and r["pasa_test_visibilidad"] is False


@pytest.mark.parametrize("categoria, sentencia, comprobar", [
    ("resolucion_espacial", "UPDATE resolucion_espacial_regiones SET activo = 0 WHERE region_nombre IN ('region 1', 'region 2')",
     lambda r: list(r["region_results"])[:2] == ["region 3", "region 4"] and "region 1" not in r["region_results"]),
    ("resolucion_contraste", "UPDATE resolucion_contraste_rois SET activo = 0 WHERE diametro_mm = 15",
     lambda r: "15mm" not in r["resultados_roi"] and len(r["resultados_roi"]) == 5),
    ("uniformidad", "UPDATE uniformidad_ruido SET activo = 0 WHERE id_region = 2",
     lambda r: "Arriba" not in r and "Superior" not in r and "Centro" in r),
    ("valores_ct", "UPDATE valores_ct SET activo = 0 WHERE id_material = 7",
     lambda r: len([x for x in r if "material" in x]) == 6 and all(x.get("material") != "Teflon" for x in r)),
])
def test_las_filas_hijas_anuladas_no_se_leen(bd_nueva, categoria, sentencia, comprobar):
    """Cada consulta de un lector filtra la vigencia de SU tabla (`filtro_activo`): una fila hija anulada no reaparece al reabrir. (Tambien lo vigilan los
    tripwires de sesion de LE4/RT1; aqui lo ve la propia prueba.)"""
    sesion = _crear_control(bd_nueva)
    datos = {"resolucion_espacial": _espacial_de_ocho_regiones(), "resolucion_contraste": _resultado_contraste((15, 9, 8, 7), (15, 9)),
             "uniformidad": _resultado_uniformidad(True, True), "valores_ct": _materiales_ct(False)}[categoria]
    assert _guardar(sesion, {categoria: datos}) == sesion
    _ejecutar(bd_nueva, sentencia)
    assert comprobar(_reabrir(bd_nueva, categoria, sesion))


@pytest.mark.parametrize("categoria, tabla, datos", [
    ("tamano_pixel", '"tamaño_pixel"', {"X": 1.0, "Y": 1.1, "imagen_analisis": None}),
    ("espesor", "espesor_corte", None), ("linealidad_ct", "linealidad_ct", None)])
def test_la_fila_unica_anulada_de_una_categoria_no_se_lee(bd_nueva, categoria, tabla, datos):
    sesion = _crear_control(bd_nueva)
    datos = datos if datos is not None else {"espesor": _resultado_espesor(2.0), "linealidad_ct": _forma_linealidad(0.999)}[categoria]
    assert _guardar(sesion, {categoria: datos}, espesor_corte=2.0, tam_px_teorico=1.074) == sesion
    assert _reabrir(bd_nueva, categoria, sesion) is not None
    _ejecutar(bd_nueva, f"UPDATE {tabla} SET activo = 0")
    assert _reabrir(bd_nueva, categoria, sesion) is None


# ---------------------------------------------------------------------------
# 10. SEGUNDA RONDA DE LA REVISION: lo guardado que el lector tiraba, el detalle parcial y el lp_cm no positivo
# ---------------------------------------------------------------------------

def test_el_diametro_minimo_visible_guardado_no_se_entrega_en_gi2_y_el_pdf_sigue_como_hoy(bd_nueva):
    """HF1 (lente reproducir) y REG-2 (lente regresion): `diametro_minimo_visible` ESTA guardado (el menor ROI visible; 7 de 8 sesiones reales) y el lector
    nunca lo entrego: el PDF dice «N/A» y la marca de no pasa en esa fila de todo control. GI.2 NO lo entrega a proposito: el constructor del PDF (GI.3) marca
    la fila de aprobado si hay valor -- presencia, no veredicto --, asi que entregarlo imprimiria una marca de aprobado por tener un numero (15 mm junto a
    «ROIs visibles: 1», que no pasa) en un documento firmado: un cambio que ninguna tarea nombra. GI.3 lo entrega en el mismo cambio que decide la marca y
    retira la entrada de CLAVES_QUE_NINGUN_LECTOR_ENTREGA_TODAVIA. Aqui: (1) el dato esta guardado; (2) el lector no lo entrega; (3) el PDF imprime lo de HEAD."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7), (15, 9))}) == sesion
    con = _leer(bd_nueva)
    try:
        assert con.execute("SELECT diametro_minimo_visible FROM resolucion_contraste").fetchone()[0] == 7        # esta guardado
    finally:
        con.close()
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)
    assert "diametro_minimo_visible" not in r["resumen"]
    fila = {f[0]: f[1:] for f in _filas_pdf(_pdf()._crear_tabla_resolucion_contraste(r))}["Diámetro mínimo visible (mm)"]
    assert fila == ["N/A", CRUZ]
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((), (15, 9))}) == sesion        # ningun ROI visible: el escritor guarda NULL
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)
    assert "diametro_minimo_visible" not in r["resumen"], "ni siquiera como None: el PDF imprimiria «None»"
    fila = {f[0]: f[1:] for f in _filas_pdf(_pdf()._crear_tabla_resolucion_contraste(r))}["Diámetro mínimo visible (mm)"]
    assert fila == ["N/A", CRUZ]


def test_con_un_detalle_parcial_de_roi_no_se_deriva_un_conteo_que_seria_falso(bd_nueva):
    """N16 (lente reproducir): el resumen dice 6 ROI y el detalle guardado trae 3 (una fila anulada): contar los visibles de 3 no es el conteo de 6. Sin
    el detalle completo no se deriva (el conteo queda None: no se inventa)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7), (15, 9))}) == sesion
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste_rois SET activo = 0 WHERE diametro_mm IN (15, 9, 8)")
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["total_rois"] == 6 and len(_reabrir(bd_nueva, "resolucion_contraste", sesion)["resultados_roi"]) == 3
    assert r["rois_visibles_visibilidad"] is None and r["pasa_test_visibilidad"] is False        # el veredicto guardado (0) tal cual: no se deriva
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste SET total_rois = NULL")
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] == 1, "sin `total_rois` guardado se deriva con el detalle que hay"


@pytest.mark.parametrize("guardado", [0, 0.0, -1, -1.0, -3.0])
def test_un_lp_cm_guardado_no_positivo_no_es_utilizable_y_se_deriva_del_nombre(guardado):
    """N17 (lente reproducir): el docstring dice «lo guardado manda cuando es un lp/cm utilizable»; un cero o un negativo no lo es (la region N vale N)."""
    assert C._lp_cm_de_la_region("region 3", guardado) == 3.0
    assert C._lp_cm_de_la_region("sin numero", guardado) is None


def test_la_unidad_de_la_fila_no_cuenta_un_lp_no_positivo():
    assert C.unidad_de_la_fila_espacial([("region 3", 0), ("region 4", -1.0)], None, None) == "lp/cm"
    assert C.unidad_de_la_fila_espacial([("region 3", 0.0)], 0.3, "region 3") == "lp/mm"


# --- los huecos que el revisor marco como «la prueba promete mas de lo que afirma» ---

class _ConexionYaAbierta:
    """Una `Conexion()` de juguete que entrega una conexion ya abierta (sin migraciones de arranque) y la cierra al terminar."""
    def __init__(self, con):
        self._con = con

    def conectar(self):
        return self._con


def test_el_tamano_de_pixel_de_una_base_sin_error_pct_tampoco_tumba_la_reapertura_completa(app, bd_nueva, monkeypatch):
    """HF4.4: el docstring de la prueba anterior prometia «no tumba la reapertura»: aqui se recorre el camino completo (todas las categorias) y la pantalla."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"tamano_pixel": {"X": 1.0, "Y": 1.2, "imagen_analisis": None}, "espesor": _resultado_espesor(2.0)},
                    espesor_corte=2.0, tam_px_teorico=1.074) == sesion
    con = sqlite3.connect(bd_nueva)
    try:
        con.execute('ALTER TABLE "tamaño_pixel" DROP COLUMN error_pct')
        con.commit()
    except sqlite3.OperationalError:
        pytest.skip("este SQLite no soporta DROP COLUMN")
    finally:
        con.close()
    todo = None
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: bd_nueva)
    Conexion._instance = None
    try:
        # sin pasar por `Conexion()` de la app: abre la base tal cual (la migracion de arranque le volveria a poner la columna)
        con = sqlite3.connect(bd_nueva)
        monkeypatch.setattr(C, "Conexion", lambda: _ConexionYaAbierta(con))
        todo = C.reconstruir_resultados_desde_bd(sesion)
    finally:
        monkeypatch.undo()
        Conexion._instance = None
    assert sorted(todo) == ["espesor", "tamano_pixel"]
    assert "Error porcentual: N/A" in C.tabla_resultados_tamano_pixel(todo["tamano_pixel"])


@pytest.mark.parametrize("sesion", [6, 12, 21, 25, 30, 34, 42, 47])
def test_las_sesiones_reales_con_resolucion_espacial_la_traen_siempre(bd_copia_real, sesion):
    """HF4.3: sin el `continue` de la version anterior (que dejaba la prueba sin asercion si la reapertura devolvia `{}`): estas ocho sesiones TIENEN la
    prueba de resolucion espacial y la reapertura tiene que traerla."""
    todo = C.reconstruir_resultados_desde_bd(sesion, categorias=["resolucion_espacial"])
    assert "resolucion_espacial" in todo, f"la sesion {sesion} perdio su resolucion espacial al reabrir"
    regiones = todo["resolucion_espacial"]["region_results"]
    assert {n: r["lp/cm"] for n, r in regiones.items()} == {f"region {n}": float(n) for n in range(1, 9)}
    assert todo["resolucion_espacial"]["unidad_guardada"] == ("lp/mm" if sesion in (6, 12, 21, 25) else "lp/cm")


def test_cada_sesion_real_reabre_con_lo_que_su_tabla_guardo(bd_copia_real):
    """HF4.2: la prueba de las diez sesiones comparaba solo los nombres de las categorias; aqui un valor de cada una contra SQL directo sobre la copia."""
    con = _leer(bd_copia_real)
    try:
        comprobadas = 0
        for sesion in SESIONES_REALES:
            todo = C.reconstruir_resultados_desde_bd(sesion)
            for fila in con.execute("SELECT id_prueba, id_tipo FROM pruebas WHERE id_sesion = ? AND (activo IS NULL OR activo = 1)", (sesion,)):
                id_prueba, id_tipo = fila["id_prueba"], fila["id_tipo"]
                categoria = ID_TIPO_INVERSO[id_tipo]
                if categoria == "espesor":
                    g = con.execute("SELECT * FROM espesor_corte WHERE id_prueba = ? AND (activo IS NULL OR activo = 1)", (id_prueba,)).fetchone()
                    assert todo["espesor"]["espesor_promedio_mm"] == g["espesor_promedio_mm"] and todo["espesor"]["error_pct"] == g["error_pct"]
                elif categoria == "tamano_pixel":
                    g = con.execute('SELECT * FROM "tamaño_pixel" WHERE id_prueba = ? AND (activo IS NULL OR activo = 1)', (id_prueba,)).fetchone()
                    assert (todo["tamano_pixel"]["X"], todo["tamano_pixel"]["Y"]) == (g["X"], g["Y"])
                elif categoria == "resolucion_contraste":
                    g = con.execute("SELECT * FROM resolucion_contraste WHERE id_prueba = ? AND (activo IS NULL OR activo = 1)", (id_prueba,)).fetchone()
                    assert todo["resolucion_contraste"]["resumen"]["total_rois"] == g["total_rois"]
                    assert len(todo["resolucion_contraste"]["resultados_roi"]) == con.execute(
                        "SELECT COUNT(*) FROM resolucion_contraste_rois WHERE id_prueba = ? AND (activo IS NULL OR activo = 1)", (id_prueba,)).fetchone()[0]
                elif categoria == "resolucion_espacial":
                    g = con.execute("SELECT * FROM resolucion_espacial WHERE id_prueba = ? AND (activo IS NULL OR activo = 1)", (id_prueba,)).fetchone()
                    assert todo["resolucion_espacial"]["resolucion_limite"]["lp_cm_maximo"] == g["lp_cm_maximo"]
                    assert todo["resolucion_espacial"]["resolucion_limite"]["ultima_region"] == g["ultima_region_exitosa"]
                elif categoria == "valores_ct":
                    n = con.execute("SELECT COUNT(*) FROM valores_ct WHERE id_prueba = ? AND (activo IS NULL OR activo = 1)", (id_prueba,)).fetchone()[0]
                    assert len([x for x in todo["valores_ct"] if "material" in x]) == n == 7
                elif categoria == "linealidad_ct":
                    g = con.execute("SELECT * FROM linealidad_ct WHERE id_prueba = ? AND (activo IS NULL OR activo = 1)", (id_prueba,)).fetchone()
                    assert todo["linealidad_ct"]["r_squared"] == g["r_cuadrado"] and todo["linealidad_ct"]["pendiente"] == g["pendiente"]
                elif categoria == "uniformidad":
                    filas = {r["nombre_region"]: r for r in con.execute(
                        "SELECT r.nombre_region, u.hu_promedio, u.desviacion FROM uniformidad_ruido u JOIN regiones_uniformidad r ON u.id_region = r.id_region "
                        "WHERE u.id_prueba = ? AND (u.activo IS NULL OR u.activo = 1)", (id_prueba,))}
                    assert todo["uniformidad"]["Centro"]["promedio_hu"] == filas["Centro"]["hu_promedio"]
                    assert todo["uniformidad"]["Arriba"]["promedio_hu"] == filas["Superior"]["hu_promedio"]
                    assert todo["uniformidad"]["Abajo"]["desviacion"] == filas["Inferior"]["desviacion"]
                comprobadas += 1
        assert comprobadas >= 40, f"la prueba debe examinar decenas de categorias reales, examino {comprobadas}"
    finally:
        con.close()


def test_los_siete_lectores_existen_y_la_reapertura_los_llama_a_todos():
    """HF4.1 (la version anterior terminaba en una tautologia): los siete lectores de la lista existen y `reconstruir_resultados_desde_bd` llama a cada uno."""
    funciones = _funciones(CATPHAN_DB)
    assert all(nombre in funciones for nombre in LECTORES)
    llamadas = {n.func.id for n in ast.walk(funciones["reconstruir_resultados_desde_bd"]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    faltan = [nombre for nombre in LECTORES if nombre not in llamadas]
    assert not faltan, f"la reapertura no llama a: {faltan}"
    assert len(LECTORES) == 7


def test_un_resumen_nulo_sin_detalle_no_inventa_el_veredicto(bd_nueva):
    """HF4.9: sin detalle por ROI el conteo queda None Y el veredicto sigue siendo el guardado (0 = no pasa), no uno derivado."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7, 6), (15, 9))}) == sesion
    _forzar_resumen_de_contraste_nulo(bd_nueva)
    _ejecutar(bd_nueva, "DELETE FROM resolucion_contraste_rois")
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] is None and r["pasa_test_visibilidad"] is False
    _ejecutar(bd_nueva, "UPDATE resolucion_contraste SET total_rois = NULL")
    r = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resumen"]
    assert r["rois_visibles_visibilidad"] is None and r["pasa_test_visibilidad"] is False, "sin detalle ni total guardado el veredicto sigue siendo el guardado"


def test_las_filas_globales_de_la_tabla_de_uniformidad_dicen_lo_guardado(app, bd_nueva):
    """N13/N14 (lente reproducir): las tres filas de resumen de la tabla de uniformidad (no uniformidad integral, indice de uniformidad y la fila extra)."""
    resultado = _resultado_uniformidad(True, False)
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": resultado}) == sesion
    filas = [f[0] for f in _celdas(C.tabla_resultados_uniformidad(_reabrir(bd_nueva, "uniformidad", sesion)))]
    resumen = [f for f in filas if f and f not in ("Centro", "Arriba", "Derecha", "Abajo", "Izquierda")]
    assert resumen[0] == "No uniformidad integral: 1.23%"
    assert resumen[1] == "Índice de uniformidad (|UI|max): 0.40%"
    assert resumen[2].startswith("Máx diferencia: 5.5 HU | Desv. global: 1.7 | ")


def test_las_filas_globales_de_la_tabla_de_uniformidad_dicen_n_a_cuando_lo_guardado_es_texto(app, bd_nueva):
    """N14 (lente reproducir): el escritor guarda 'No disponible' en las columnas de `uniformidad_global` cuando el analisis no trajo el dato; reabierto, las dos
    primeras filas globales dicen N/A (ni un 0.00 inventado ni una excepcion que tumbe la tabla)."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": _resultado_uniformidad(True, False)}) == sesion
    _ejecutar(bd_nueva, "UPDATE uniformidad_global SET integral_non_uniformity_pct = 'No disponible', uniformity_index_max = 'No disponible'")
    filas = [f[0] for f in _celdas(C.tabla_resultados_uniformidad(_reabrir(bd_nueva, "uniformidad", sesion)))]
    resumen = [f for f in filas if f and f not in ("Centro", "Arriba", "Derecha", "Abajo", "Izquierda")]
    assert resumen[0] == "No uniformidad integral: N/A" and resumen[1] == "Índice de uniformidad (|UI|max): N/A", resumen


# ---------------------------------------------------------------------------
# 11. LA CLASE (lente regresion): la reapertura no construye pantallas que nadie va a usar
# ---------------------------------------------------------------------------

CONSTRUCTORES_DE_PANTALLA = ("tabla_resultados_espesor", "tabla_resultados_tamano_pixel", "tabla_resultados_resolucion_contraste",
                             "tabla_resultados_resolucion_espacial", "tabla_resultados_ct", "tabla_resultados_linealidad_ct",
                             "tabla_resultados_uniformidad")


def _guardar_las_siete(bd_nueva):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {
        "espesor": _resultado_espesor(2.0), "tamano_pixel": {"X": 1.0, "Y": 1.1, "imagen_analisis": None},
        "resolucion_contraste": _resultado_contraste((15, 9, 8, 7), (15, 9)), "resolucion_espacial": _espacial_de_ocho_regiones(),
        "valores_ct": _materiales_ct(False), "linealidad_ct": _forma_linealidad(0.999), "uniformidad": _resultado_uniformidad(True, True)},
        espesor_corte=2.0, tam_px_teorico=1.074) == sesion
    return sesion


def test_sin_label_la_reapertura_no_construye_las_pantallas_y_ningun_constructor_la_vacia(app, bd_nueva, monkeypatch):
    """La causa de fondo de «un valor inesperado vacia la reapertura entera»: `reconstruir_resultados_desde_bd` construia el QTableWidget (o el texto) de CADA
    categoria aunque no hubiera donde ponerlo (el PDF mensual y el anual, y la carga de Valores CT para la linealidad llaman sin `label`), y la excepcion de UN
    constructor devolvia `{}` para todas. Se prueba haciendo que TODO constructor de pantalla lance: sin `label` la reapertura trae las siete categorias."""
    sesion = _guardar_las_siete(bd_nueva)
    llamadas = []

    def explota(nombre):
        def _f(*args, **kwargs):
            llamadas.append(nombre)
            raise RuntimeError(f"constructor de pantalla {nombre}")
        return _f
    for nombre in CONSTRUCTORES_DE_PANTALLA:
        monkeypatch.setattr(C, nombre, explota(nombre))
    _con_la_base(bd_nueva, monkeypatch)
    try:
        todo = C.reconstruir_resultados_desde_bd(sesion)
    finally:
        _cerrar_la_base()
    assert sorted(todo) == sorted(ID_TIPO), f"la reapertura sin label perdio categorias: {sorted(todo)}"
    assert llamadas == [], f"se construyeron pantallas que nadie iba a usar: {llamadas}"


def test_con_label_la_reapertura_si_construye_la_pantalla_de_cada_categoria(app, bd_nueva, monkeypatch):
    """Lo que NO cambia: cuando hay un `label` (la pestana de la pantalla) cada categoria construye su tabla como hasta hoy."""
    from PyQt5.QtWidgets import QLabel
    sesion = _guardar_las_siete(bd_nueva)
    llamadas = []
    for nombre in CONSTRUCTORES_DE_PANTALLA:
        original = getattr(C, nombre)

        def espia(*args, _o=original, _n=nombre, **kwargs):
            llamadas.append(_n)
            return _o(*args, **kwargs)
        monkeypatch.setattr(C, nombre, espia)
    _con_la_base(bd_nueva, monkeypatch)
    label = QLabel()                               # sin padre: `usar_label_seguro` no hace nada, pero el constructor corre como siempre
    try:
        todo = C.reconstruir_resultados_desde_bd(sesion, label=label)
    finally:
        _cerrar_la_base()
    assert sorted(todo) == sorted(ID_TIPO)
    assert sorted(llamadas) == sorted(CONSTRUCTORES_DE_PANTALLA), llamadas


# ---------------------------------------------------------------------------
# 12. LA CLASE (lentes reproducir y regresion): un constructor que lee una clave que ningun lector entrega imprime «N/A» y nadie se entera
# ---------------------------------------------------------------------------

PDF_IMAGENES = RAIZ / "models" / "PDF" / "Imagenes" / "reportes_control_sistema_imagenes.py"

# categoria -> (lector, constructor de la pantalla de lo guardado, constructor de la tabla del PDF)
CONSUMIDORES = {
    "espesor": ("reconstruir_espesor_corte", "tabla_resultados_espesor", "_crear_tabla_espesor_corte"),
    "tamano_pixel": ("reconstruir_tamano_pixel", "tabla_resultados_tamano_pixel", "_crear_tabla_tamano_pixel"),
    "resolucion_contraste": ("reconstruir_resolucion_contraste", "tabla_resultados_resolucion_contraste", "_crear_tabla_resolucion_contraste"),
    "resolucion_espacial": ("reconstruir_resolucion_espacial", "tabla_resultados_resolucion_espacial", "_crear_tabla_resolucion_espacial"),
    "valores_ct": ("reconstruir_valores_ct", "tabla_resultados_ct", "_crear_tabla_valores_ct"),
    "linealidad_ct": ("reconstruir_linealidad_ct", "tabla_resultados_linealidad_ct", "_crear_tabla_linealidad_ct"),
    "uniformidad": ("reconstruir_uniformidad", "tabla_resultados_uniformidad", "_crear_tabla_uniformidad"),
}

# Las claves que un constructor lee y NINGUN lector entrega, HOY. Lista REVISADA, corta y con su motivo. Solo puede achicarse: la prueba falla si aparece una
# nueva (el constructor imprimiria «N/A» o su valor por omision sin que nadie lo haya decidido) y tambien si una entrada deja de ser cierta (el lector ya la
# entrega: hay que retirarla de aqui). Las que son de GI.3 las retira GI.3 en el mismo cambio que las entrega.
CLAVES_QUE_NINGUN_LECTOR_ENTREGA_TODAVIA = {
    ("PDF", "_crear_tabla_resolucion_contraste"): {
        "diametro_minimo_visible": "guardado (el menor ROI visible); GI.3 lo entrega con la marca de su fila: el PDF pone la marca de aprobado si HAY valor, "
                                   "no si el control pasa, y entregarlo en GI.2 imprimiria un cambio que ninguna tarea nombra"},
    ("PDF", "_crear_tabla_uniformidad"): {
        "hu_promedio": "el PDF lee `hu_promedio` y el analisis y el lector dicen `promedio_hu`: GI.3 pasa el PDF a `promedio_hu`"},
    ("pantalla", "tabla_resultados_espesor"): {
        "factor_correccion": "solo lo trae el analisis fresco; lo reabierto no lo inventa (D4)",
        "num_rampas_detectadas": "solo lo trae el analisis fresco; lo reabierto no lo inventa (D4)",
        "combinacion_slices": "solo lo trae el analisis fresco; lo reabierto no lo inventa (D4)",
        "espesores_individuales": "solo lo trae el analisis fresco; lo reabierto no lo inventa (D4)"},
    ("pantalla", "tabla_resultados_resolucion_contraste"): {
        "visibility_threshold": "no se guarda ni el analisis lo produce con ese nombre: la pantalla dice «Umbral: N/A» (anterior a GI.2; lo decide GI.3)"},
    ("pantalla", "tabla_resultados_ct"): {
        "resultados": "la tabla tambien acepta el diccionario del analisis fresco `{'resultados': [...]}`; lo reabierto es la lista misma"},
}


def _claves_que_entrega(funcion):
    """Claves de texto que un LECTOR escribe en lo que devuelve: las de los diccionarios literales y las de `x['clave'] = ...`."""
    claves = set()
    for nodo in ast.walk(funcion):
        if isinstance(nodo, ast.Dict):
            claves |= {k.value for k in nodo.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if isinstance(nodo, ast.Subscript) and isinstance(nodo.ctx, ast.Store) and isinstance(nodo.slice, ast.Constant) and isinstance(nodo.slice.value, str):
            claves.add(nodo.slice.value)
    return claves


def _claves_que_lee(funcion):
    """Claves de texto que un CONSTRUCTOR lee de lo reabierto: `x.get('clave')` y `x['clave']`."""
    claves = set()
    for nodo in ast.walk(funcion):
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "get" and nodo.args \
                and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str):
            claves.add(nodo.args[0].value)
        if isinstance(nodo, ast.Subscript) and isinstance(nodo.ctx, ast.Load) and isinstance(nodo.slice, ast.Constant) and isinstance(nodo.slice.value, str):
            claves.add(nodo.slice.value)
    return claves


def _huecos_de_los_consumidores():
    """{(pantalla|PDF, constructor): claves que lee y su lector no entrega}, y el numero de lecturas y entregas examinadas por categoria."""
    en_db, en_pdf = _funciones(CATPHAN_DB), _funciones(PDF_IMAGENES)
    huecos, examinado = {}, {}
    for categoria, (lector, pantalla, tabla) in CONSUMIDORES.items():
        entregadas = _claves_que_entrega(en_db[lector])
        for etiqueta, funcion in (("pantalla", en_db[pantalla]), ("PDF", en_pdf[tabla])):
            leidas = _claves_que_lee(funcion)
            examinado[(etiqueta, funcion.name)] = (len(leidas), len(entregadas))
            if leidas - entregadas:
                huecos[(etiqueta, funcion.name)] = leidas - entregadas
    return huecos, examinado


def test_toda_clave_que_un_constructor_lee_la_entrega_un_lector_o_esta_en_la_lista_revisada():
    """La clase del hallazgo `diametro_minimo_visible`: el lector selecciona una columna y la descarta, y el constructor del PDF o de la pantalla lee una clave
    que nadie entrega y imprime «N/A»/«None» en un documento firmado sin que ninguna prueba lo vea. Aqui se cruza, por AST, lo que cada uno de los CATORCE
    constructores (siete de la pantalla de lo guardado, siete del PDF) lee contra lo que su lector entrega."""
    huecos, _ = _huecos_de_los_consumidores()
    revisadas = {consumidor: set(claves) for consumidor, claves in CLAVES_QUE_NINGUN_LECTOR_ENTREGA_TODAVIA.items()}
    nuevos = {c: sorted(h - revisadas.get(c, set())) for c, h in huecos.items() if h - revisadas.get(c, set())}
    assert not nuevos, f"un constructor lee una clave que ningun lector entrega (decidir: entregarla o revisarla en la lista con su motivo): {nuevos}"
    caducadas = {c: sorted(k - huecos.get(c, set())) for c, k in revisadas.items() if k - huecos.get(c, set())}
    assert not caducadas, f"la lista revisada trae claves que el lector ya entrega (o que el constructor ya no lee): retirarlas. {caducadas}"


def test_cada_clave_revisada_tiene_su_motivo():
    for consumidor, claves in CLAVES_QUE_NINGUN_LECTOR_ENTREGA_TODAVIA.items():
        for clave, motivo in claves.items():
            assert isinstance(motivo, str) and len(motivo) > 20, (consumidor, clave)


def test_el_censo_de_claves_examina_los_catorce_constructores_y_los_siete_lectores():
    """No es vacuo: cada constructor lee al menos tres claves de texto y cada lector entrega al menos cuatro; sin eso el cruce de arriba no probaria nada."""
    _, examinado = _huecos_de_los_consumidores()
    assert len(examinado) == 14
    for (etiqueta, funcion), (leidas, entregadas) in examinado.items():
        assert leidas >= 3 and entregadas >= 4, (etiqueta, funcion, leidas, entregadas)


def test_el_censo_de_claves_ve_una_clave_que_el_lector_no_entrega():
    """El cruce discrimina: sobre un lector que entrega {a, b} y dos constructores que leen {a, c} y {b} el unico hueco es `c`; si el lector entrega `c`, ninguno."""
    def hueco(lector, constructor):
        return _claves_que_lee(ast.parse(constructor).body[0]) - _claves_que_entrega(ast.parse(lector).body[0])
    lector = "def r():\n    d = {'a': 1}\n    d['b'] = 2\n    return d\n"
    assert hueco(lector, "def p(x):\n    return x.get('a'), x['c']\n") == {"c"}
    assert hueco(lector, "def p(x):\n    return x['b']\n") == set()
    assert hueco(lector.replace("d['b'] = 2", "d['b'] = 2\n    d['c'] = 3"), "def p(x):\n    return x.get('a'), x['c']\n") == set()
